"""HTTP endpoints for interacting with vouchers."""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404
import django_filters
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from rest_framework import filters, status
from rest_framework.response import Response
from rest_framework_extensions.decorators import action
from slumber.exceptions import SlumberBaseException

from ecommerce.core.constants import DEFAULT_CATALOG_PAGE_SIZE
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.models import Course
from ecommerce.courses.utils import get_course_info_from_lms
from ecommerce.coupons.views import get_voucher_and_products_from_code
from ecommerce.extensions.api import exceptions, serializers
from ecommerce.extensions.api.permissions import IsOffersOrIsAuthenticatedAndStaff
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet


logger = logging.getLogger(__name__)
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


class VoucherFilter(django_filters.FilterSet):
    """
    Filter for vouchers via query string parameters.
    Currently supports filtering via the voucher's code.
    """
    code = django_filters.CharFilter(name='code', lookup_type='exact')

    class Meta(object):
        model = Voucher
        fields = ('code', )


class VoucherViewSet(NonDestroyableModelViewSet):
    """ View set for vouchers. """
    queryset = Voucher.objects.all()
    serializer_class = serializers.VoucherSerializer
    permission_classes = (IsOffersOrIsAuthenticatedAndStaff, )
    filter_backends = (filters.DjangoFilterBackend, )
    filter_class = VoucherFilter

    @action(is_for_list=True, methods=['get'], endpoint='offers')
    def offers(self, request):
        """
        Preview the courses offered by the voucher.
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
            voucher, products = get_voucher_and_products_from_code(code)
        except Voucher.DoesNotExist:
            logger.error('Voucher with code %s not found.', code)
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except exceptions.ProductNotFoundError:
            logger.error('No product(s) are associated with this code.')
            return Response(status=status.HTTP_400_BAD_REQUEST)

        query = voucher.offers.first().benefit.range.catalog_query
        if query:
            cache_key = 'voucher_offers_{}'.format(query)
        else:
            cache_key = 'voucher_offers_{}'.format(voucher.id)

        cache_hash = hashlib.md5(cache_key).hexdigest()
        offers = cache.get(cache_hash)
        if not offers:
            try:
                offers = self.get_offers(products, request, voucher)
            except (ConnectionError, SlumberBaseException, Timeout):
                logger.error('Could not get course information.')
                return Response(status=status.HTTP_400_BAD_REQUEST)
            except Http404:
                logger.error('Could not get information for product %s.', products[0].title)
                return Response(status=status.HTTP_404_NOT_FOUND)
            cache.set(cache_hash, offers, settings.COURSES_API_CACHE_TIMEOUT)

        page = self.paginate_queryset(offers)
        return self.get_paginated_response(page)

    def get_offers(self, products, request, voucher):
        """
        Get the course offers associated with the voucher.
        Arguments:
            products (List): List of Products associated with the voucher
            request (HttpRequest): Request data
            voucher (Voucher): Oscar Voucher for which the offers are returned
        Returns:
            List: List of course offers where each offer is represented by a dictionary
        """
        benefit = voucher.offers.first().benefit
        catalog_query = benefit.range.catalog_query
        offers = []
        if catalog_query:
            query_results = request.site.siteconfiguration.course_catalog_api_client.course_runs.get(
                q=catalog_query,
                page_size=DEFAULT_CATALOG_PAGE_SIZE,
                limit=DEFAULT_CATALOG_PAGE_SIZE
            )['results']

            course_ids = [product.course_id for product in products]
            courses = Course.objects.filter(id__in=course_ids)
            stock_records = StockRecord.objects.filter(product__in=products)
            contains_verified_course = (benefit.range.course_seat_types == 'verified')

            for product in products:
                # Omit unavailable seats from the offer results so that one seat does not cause an
                # error message for every seat in the query result.
                if not request.strategy.fetch_for_product(product).availability.is_available_to_buy:
                    logger.info('%s is unavailable to buy. Omitting it from the results.', product)
                    continue
                course_id = product.course_id
                course_catalog_data = next((result for result in query_results if result['key'] == course_id), None)

                try:
                    stock_record = stock_records.get(product__id=product.id)
                except StockRecord.DoesNotExist:
                    stock_record = None
                    logger.error('Stock Record for product %s not found.', product.id)

                try:
                    course = courses.get(id=course_id)
                except Course.DoesNotExist:
                    course = None
                    logger.error('Course %s not found.', course_id)

                if course_catalog_data and course and stock_record:
                    offers.append(self.get_course_offer_data(
                        benefit=benefit,
                        course=course,
                        course_info=course_catalog_data,
                        is_verified=contains_verified_course,
                        stock_record=stock_record,
                        voucher=voucher
                    ))
        else:
            product = products[0]
            course_id = product.course_id
            course = get_object_or_404(Course, id=course_id)
            stock_record = get_object_or_404(StockRecord, product__id=product.id)
            course_info = get_course_info_from_lms(course_id)

            if course_info:
                course_info['image'] = {'src': get_lms_url(course_info['media']['course_image']['uri'])}

                offers.append(self.get_course_offer_data(
                    benefit=benefit,
                    course=course,
                    course_info=course_info,
                    is_verified=(course.type == 'verified'),
                    stock_record=stock_record,
                    voucher=voucher
                ))
        return offers

    def get_course_offer_data(self, benefit, course, course_info, is_verified, stock_record, voucher):
        """
        Gets course offer data.
        Arguments:
            benefit (Benefit): Benefit associated with a voucher
            course (Course): Course associated with a voucher
            course_info (dict): Course info fetched from an API (LMS or Course Catalog)
            is_verified (bool): Indicated whether or not the voucher's range of products contains a verified course seat
            stock_record (StocRecord): Stock record associated with the course seat
            voucher (Voucher): Voucher for which the course offer data is being fetched
        Returns:
            dict: Course offer data
        """
        return {
            'benefit': serializers.BenefitSerializer(benefit).data,
            'contains_verified': is_verified,
            'course_start_date': course_info['start'],
            'id': course.id,
            'image_url': course_info['image']['src'],
            'organization': CourseKey.from_string(course.id).org,
            'seat_type': course.type,
            'stockrecords': serializers.StockRecordSerializer(stock_record).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime,
        }
