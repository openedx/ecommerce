"""HTTP endpoints for interacting with vouchers."""
import logging
from urlparse import urlparse

import django_filters
from dateutil import parser
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from rest_framework import filters, status
from rest_framework.decorators import list_route
from rest_framework.response import Response
from slumber.exceptions import SlumberBaseException

from ecommerce.core.constants import DEFAULT_CATALOG_PAGE_SIZE
from ecommerce.coupons.utils import fetch_course_catalog, get_catalog_course_runs
from ecommerce.courses.models import Course
from ecommerce.courses.utils import get_course_info_from_catalog
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.permissions import IsOffersOrIsAuthenticatedAndStaff
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


class VoucherFilter(django_filters.FilterSet):
    """
    Filter for vouchers via query string parameters.
    Currently supports filtering via the voucher's code.
    """
    code = django_filters.CharFilter(name='code')

    class Meta(object):
        model = Voucher
        fields = ('code',)


class VoucherViewSet(NonDestroyableModelViewSet):
    """ View set for vouchers. """
    serializer_class = serializers.VoucherSerializer
    permission_classes = (IsOffersOrIsAuthenticatedAndStaff,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = VoucherFilter

    def get_queryset(self):
        return Voucher.objects.filter(
            coupon_vouchers__coupon__stockrecords__partner=self.request.site.siteconfiguration.partner
        )

    @list_route()
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
        except (ConnectionError, SlumberBaseException, Timeout):
            logger.error('Could not connect to Discovery Service.')
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
        all_course_ids = []
        nonexpired_course_ids = []
        for result in results:
            all_course_ids.append(result['key'])
            if not result['enrollment_end'] or \
                    (result['enrollment_end'] and parser.parse(result['enrollment_end']) > now()):
                nonexpired_course_ids.append(result['key'])

        products = []
        for seat_type in course_seat_types.split(','):
            products.extend(Product.objects.filter(
                course_id__in=nonexpired_course_ids if seat_type == 'professional' else all_course_ids,
                attributes__name='certificate_type',
                attribute_values__value_text=seat_type
            ))
        stock_records = StockRecord.objects.filter(product__in=products)
        return products, stock_records

    def get_offers_from_query(self, request, voucher, catalog_query):
        """ Helper method for collecting offers from catalog query.

        Args:
            request (WSGIRequest): Request data.
            voucher (Voucher): Oscar Voucher for which the offers are returned.
            catalog_query (str): The query for the Course Discovery.

        Returns:
            A list of dictionaries with retrieved offers and a link to the next
            page of the Course Discovery results.
            """
        offers = []
        benefit = voucher.offers.first().benefit
        course_seat_types = benefit.range.course_seat_types
        multiple_credit_providers = False
        credit_provider_price = None

        response = get_catalog_course_runs(
            site=request.site,
            query=catalog_query,
            limit=request.GET.get('limit', DEFAULT_CATALOG_PAGE_SIZE),
            offset=request.GET.get('offset'),
        )
        next_page = response['next']
        products, stock_records = self.retrieve_course_objects(response['results'], course_seat_types)
        contains_verified_course = (course_seat_types == 'verified')
        for product in products:
            # Omit unavailable seats from the offer results so that one seat does not cause an
            # error message for every seat in the query result.
            if not request.strategy.fetch_for_product(product).availability.is_available_to_buy:
                logger.info('%s is unavailable to buy. Omitting it from the results.', product)
                continue

            course_id = product.course_id
            course_catalog_data = next(
                (result for result in response['results'] if result['key'] == course_id),
                None
            )
            if course_seat_types == 'credit':
                # Omit credit seats for which the user is not eligible or which the user already bought.
                if request.user.is_eligible_for_credit(product.course_id):
                    if Order.objects.filter(user=request.user, lines__product=product).exists():
                        continue
                else:
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
        benefit = voucher.offers.first().benefit
        catalog_query = benefit.range.catalog_query
        catalog_id = benefit.range.course_catalog
        next_page = None
        offers = []

        if catalog_id:
            catalog = fetch_course_catalog(request.site, catalog_id)
            catalog_query = catalog.get("query") if catalog else catalog_query

        if catalog_query:
            offers, next_page = self.get_offers_from_query(request, voucher, catalog_query)
        else:
            product_range = voucher.offers.first().benefit.range
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
                    benefit=benefit,
                    course=course,
                    course_info=course_info,
                    credit_provider_price=None,
                    multiple_credit_providers=False,
                    is_verified=(course.type == 'verified'),
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
        try:
            image = course_info['image']['src']
        except (KeyError, TypeError):
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
