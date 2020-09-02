"""HTTP endpoints for interacting with vouchers."""


import logging
from urllib.parse import urlparse

import django_filters
import pytz
from dateutil.parser import parse
from dateutil.utils import default_tzinfo
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from slumber.exceptions import SlumberBaseException

from ecommerce.core.constants import DEFAULT_CATALOG_PAGE_SIZE
from ecommerce.coupons.utils import fetch_course_catalog, get_catalog_course_runs
from ecommerce.courses.models import Course
from ecommerce.courses.utils import get_course_info_from_catalog
from ecommerce.enterprise.utils import get_enterprise_catalog
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.permissions import IsOffersOrIsAuthenticatedAndStaff
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


class VoucherFilter(django_filters.rest_framework.FilterSet):
    """
    Filter for vouchers via query string parameters.
    Currently supports filtering via the voucher's code.
    """
    code = django_filters.CharFilter(field_name='code')

    class Meta:
        model = Voucher
        fields = ('code',)


class VoucherViewSet(NonDestroyableModelViewSet):
    """ View set for vouchers. """
    serializer_class = serializers.VoucherSerializer
    permission_classes = (IsOffersOrIsAuthenticatedAndStaff,)
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = VoucherFilter

    def get_queryset(self):
        return Voucher.objects.filter(
            coupon_vouchers__coupon__stockrecords__partner=self.request.site.siteconfiguration.partner
        )

    @action(detail=False)
    def offers(self, request):
        """ Preview the courses offered by the voucher.

        Paginated Response containing the list of course offers will be returned.
        ---
        parameters:
            - name: code
              description: Voucher code
              required: true
              type: string
              paramType: query
              multiple: false
        """
        code = request.GET.get('code', '')

        try:
            voucher = Voucher.objects.get(code=code)
        except Voucher.DoesNotExist:
            logger.error('Voucher with code %s not found.', code)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            offers_data = self.get_offers(request, voucher)
        except (ReqConnectionError, SlumberBaseException, Timeout):
            logger.exception('Could not connect to Discovery Service.')
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except Product.DoesNotExist:
            logger.error('Could not locate product for voucher with code %s.', code)
            return Response(status=status.HTTP_404_NOT_FOUND)

        next_page = offers_data['next']
        if next_page:
            next_page_query = urlparse(next_page).query
            offers_data['next'] = '{path}?{query}&code={code}'.format(
                code=code,
                path=request.path,
                query=next_page_query,
            )
        return Response(data=offers_data)

    def retrieve_course_objects(self, results, course_seat_types):
        """ Helper method to retrieve all the courses, products and stock records
        from course IDs in course catalog response results. Professional courses
        which have a set enrollment end date and which has passed are omitted.

        Args:
            results(dict): Course catalog response results.
            course_seat_types(str): Comma-separated list of accepted seat types.

        Returns:
            Querysets of products and stock records retrieved from results.
        """
        course_run_metadata = {}

        def is_course_run_enrollable(course_run):
            # Checks if a course run is available for enrollment by checking the following conditions:
            #   if end date is not set or is in the future
            #   if enrollment start is not set or is in the past
            #   if enrollment end is not set or is in the future
            end = course_run.get('end') and default_tzinfo(parse(course_run['end']), pytz.UTC)
            enrollment_start = (course_run.get('enrollment_start') and
                                default_tzinfo(parse(course_run['enrollment_start']), pytz.UTC))
            enrollment_end = (course_run.get('enrollment_end') and
                              default_tzinfo(parse(course_run['enrollment_end']), pytz.UTC))
            current_time = now()

            return (
                (not end or end > current_time) and
                (not enrollment_start or enrollment_start <= current_time) and
                (not enrollment_end or enrollment_end > current_time)
            )

        for result in results:
            if 'content_type' in result and result['content_type'] == 'course':
                for course_run in result['course_runs']:
                    if is_course_run_enrollable(course_run):
                        course_run_metadata[course_run['key']] = course_run
                        # Copy over title and image from course to course_run metadata,
                        # which get used to display the offer.
                        course_run_metadata[course_run['key']]['title'] = result['title']
                        course_run_metadata[course_run['key']]['card_image_url'] = result['card_image_url']
            elif is_course_run_enrollable(result):
                course_run_metadata[result['key']] = result

        products = []
        for seat_type in course_seat_types.split(','):
            products.extend(Product.objects.filter(
                course_id__in=list(course_run_metadata.keys()),
                attributes__name='certificate_type',
                attribute_values__value_text=seat_type
            ))
        stock_records = StockRecord.objects.filter(product__in=products)
        return products, stock_records, course_run_metadata

    def convert_catalog_response_to_offers(self, request, voucher, response):
        offers = []
        benefit = voucher.best_offer.benefit
        # default course_seat_types value to all paid seat types.
        course_seat_types = 'verified,professional,credit'
        if benefit.range and benefit.range.course_seat_types:
            course_seat_types = benefit.range.course_seat_types
        multiple_credit_providers = False
        credit_provider_price = None

        logger.info('[Voucher Offers] CourseSeatTypes: [%s], Voucher: [%s]', course_seat_types, voucher.id)

        products, stock_records, course_run_metadata = self.retrieve_course_objects(
            response['results'], course_seat_types
        )
        contains_verified_course = ('verified' in course_seat_types)
        for product in products:
            logger.info('[Voucher Offers] Constructing offer data. Product: [%s]', product.id)
            # Omit unavailable seats from the offer results so that one seat does not cause an
            # error message for every seat in the query result.
            if not request.strategy.fetch_for_product(product).availability.is_available_to_buy:
                logger.info('%s is unavailable to buy. Omitting it from the results.', product)
                continue

            course_id = product.course_id
            course_catalog_data = course_run_metadata[course_id]
            if course_seat_types == 'credit' or product.attr.certificate_type == 'credit':
                logger.info('[Voucher Offers] Constructing offer data for credit.')
                # Omit credit seats for which the user is not eligible or which the user already bought.
                if not request.user.is_eligible_for_credit(product.course_id, request.site.siteconfiguration):
                    continue
                if Order.objects.filter(user=request.user, lines__product=product).exists():
                    continue
                credit_seats = Product.objects.filter(parent=product.parent, attributes__name='credit_provider')

                if credit_seats.count() > 1:
                    multiple_credit_providers = True
                    credit_provider_price = None
                else:
                    multiple_credit_providers = False
                    credit_provider_price = StockRecord.objects.get(product=product).price_excl_tax

            try:
                stock_record = stock_records.get(product__id=product.id)
            except StockRecord.DoesNotExist:
                stock_record = None
                logger.error('Stock Record for product %s not found.', product.id)

            try:
                course = Course.objects.get(id=course_id)
            except Course.DoesNotExist:  # pragma: no cover
                course = None
                logger.error('Course %s not found.', course_id)

            if course_catalog_data and course and stock_record:
                offers.append(self.get_course_offer_data(
                    benefit=benefit,
                    course=course,
                    course_info=course_catalog_data,
                    credit_provider_price=credit_provider_price,
                    multiple_credit_providers=multiple_credit_providers,
                    is_verified=contains_verified_course,
                    product=product,
                    stock_record=stock_record,
                    voucher=voucher
                ))

        return offers

    def get_offers_from_catalog(self, request, voucher):
        """ Helper method for collecting offers from catalog query or enterprise catalog.

        Args:
            request (WSGIRequest): Request data.
            voucher (Voucher): Oscar Voucher for which the offers are returned.

        Returns:
            A list of dictionaries with retrieved offers and a link to the next
            page of the Course Discovery results.
            """
        benefit = voucher.best_offer.benefit
        condition = voucher.best_offer.condition

        # Pull all catalog related data from the offer.
        catalog_query = benefit.range.catalog_query if benefit.range else None
        catalog_id = benefit.range.course_catalog if benefit.range else None
        enterprise_customer = (condition.enterprise_customer_uuid or
                               (benefit.range and benefit.range.enterprise_customer))
        enterprise_catalog = (condition.enterprise_customer_catalog_uuid or
                              (benefit.range and benefit.range.enterprise_customer_catalog))

        if catalog_id:
            catalog = fetch_course_catalog(request.site, catalog_id)
            catalog_query = catalog.get("query") if catalog else catalog_query

        # There is no catalog related data specified for this condition, so return None.
        if not catalog_query and not enterprise_customer:
            return None, None

        if enterprise_catalog:
            response = get_enterprise_catalog(
                site=request.site,
                enterprise_catalog=enterprise_catalog,
                limit=request.GET.get('limit', DEFAULT_CATALOG_PAGE_SIZE),
                page=request.GET.get('page'),
            )
        elif catalog_query:
            response = get_catalog_course_runs(
                site=request.site,
                query=catalog_query,
                limit=request.GET.get('limit', DEFAULT_CATALOG_PAGE_SIZE),
                offset=request.GET.get('offset'),
            )
        else:
            logger.warning(
                'User is trying to redeem Voucher %s, but no catalog information is configured!',
                voucher.code
            )
            return [], None

        next_page = response['next']
        offers = self.convert_catalog_response_to_offers(request, voucher, response)

        return offers, next_page

    def get_offers(self, request, voucher):
        """
        Get the course offers associated with the voucher.
        Arguments:
            request (HttpRequest): Request data.
            voucher (Voucher): Oscar Voucher for which the offers are returned.
        Returns:
            dict: Dictionary containing a link to the next page of Course Discovery results and
                  a List of course offers where each offer is represented as a dictionary.
        """
        offers, next_page = self.get_offers_from_catalog(request, voucher)
        if offers is None:
            offers = []
            product_range = voucher.best_offer.benefit.range
            products = product_range.all_products()
            if products:
                product = products[0]
            else:
                raise Product.DoesNotExist
            course_id = product.course_id
            course = get_object_or_404(Course, id=course_id)
            stock_record = get_object_or_404(StockRecord, product__id=product.id)
            course_info = get_course_info_from_catalog(request.site, product)

            if course_info:
                offers.append(self.get_course_offer_data(
                    benefit=voucher.best_offer.benefit,
                    course=course,
                    course_info=course_info,
                    credit_provider_price=None,
                    multiple_credit_providers=False,
                    is_verified=(course.type == 'verified' or course.type == 'verified-only'),
                    product=product,
                    stock_record=stock_record,
                    voucher=voucher
                ))

        return {'next': next_page, 'results': offers}

    def get_course_offer_data(
            self, benefit, course, course_info, credit_provider_price, is_verified,
            multiple_credit_providers, product, stock_record, voucher
    ):
        """
        Gets course offer data.
        Arguments:
            benefit (Benefit): Benefit associated with a voucher
            course (Course): Course associated with a voucher
            course_info (dict): Course info fetched from an API (LMS or Discovery)
            is_verified (bool): Indicated whether or not the voucher's range of products contains a verified course seat
            stock_record (StockRecord): Stock record associated with the course seat
            voucher (Voucher): Voucher for which the course offer data is being fetched
        Returns:
            dict: Course offer data
        """
        if course_info.get('image') and 'src' in course_info['image']:
            image = course_info['image']['src']
        elif 'card_image_url' in course_info:
            image = course_info['card_image_url']
        else:
            image = ''
        return {
            'benefit': serializers.BenefitSerializer(benefit).data,
            'contains_verified': is_verified,
            'course_start_date': course_info.get('start', ''),
            'id': course.id,
            'image_url': image,
            'multiple_credit_providers': multiple_credit_providers,
            'organization': CourseKey.from_string(course.id).org,
            'credit_provider_price': credit_provider_price,
            'seat_type': product.attr.certificate_type,
            'stockrecords': serializers.StockRecordSerializer(stock_record).data,
            'title': course_info.get('title', course.name),
            'voucher_end_date': voucher.end_datetime
        }
