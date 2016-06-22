"""HTTP endpoints for interacting with vouchers."""
import hashlib
import logging

from django.conf import settings
from django.core.cache import cache
import django_filters
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from rest_framework import filters, status
from rest_framework.response import Response
from rest_framework_extensions.decorators import action
from slumber.exceptions import SlumberBaseException

from ecommerce.core.constants import DEFAULT_CATALOG_PAGE_SIZE
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
        cache_key = 'catalog_query_{}'.format(query)
        cache_hash = hashlib.md5(cache_key).hexdigest()
        offers = cache.get(cache_hash)
        if not offers:  # pragma: no cover
            try:
                offers = self.get_offers(products, request, voucher)
            except (ConnectionError, SlumberBaseException, Timeout):
                logger.error('Could not get course information.')
                return Response(status=status.HTTP_400_BAD_REQUEST)
            cache.set(cache_hash, offers, settings.COURSES_API_CACHE_TIMEOUT)

        page = self.paginate_queryset(offers)
        return self.get_paginated_response(page)

    def _get_offers_for_product(self, product, voucher, course_info=None, offers=None):
        """
        Retrieves product-specific offers based on the course and benefit information
        """
        course_id = product.course_id
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return offers if offers else []

        try:
            stock_record = StockRecord.objects.get(product__id=product.id)
        except StockRecord.DoesNotExist:
            return offers if offers else []

        if not course_info:
            course_info = get_course_info_from_lms(course_id)
            course_info['image'] = {'src': course_info['media']['image']['raw']}

        benefit = self._get_voucher_benefit(voucher)

        if benefit and course_info:

            if offers is None:
                offers = []
            offers.append({
                'benefit': serializers.BenefitSerializer(benefit).data,
                'contains_verified': (course.type == 'verified'),
                'course_start_date': course_info['start'],
                'id': course.id,
                'image_url': course_info['image']['src'],
                'organization': CourseKey.from_string(course.id).org,
                'seat_type': course.type,
                'stockrecords': serializers.StockRecordSerializer(stock_record).data,
                'title': course.name,
                'voucher_end_date': voucher.end_datetime,
            })

        return offers

    def _get_offers_for_catalog_query(self, request, products, voucher):
        """
        Batch workflow to retrieve product offers for a given catalog query
        """
        catalog_query = self._get_voucher_catalog_query(voucher)
        client = request.site.siteconfiguration.course_catalog_api_client
        try:
            response = client.course_runs.get(
                q=catalog_query,
                page_size=DEFAULT_CATALOG_PAGE_SIZE,
                limit=DEFAULT_CATALOG_PAGE_SIZE
            )
        except (ConnectionError, SlumberBaseException, Timeout):  # pragma: no cover
            logger.error('Could not get course run information.')
            return Response(status=status.HTTP_400_BAD_REQUEST)

        query_results = []
        if 'results' in response:
            query_results = response['results']

        offers = []
        for product in products:
            course_id = product.course_id
            course_info = next((result for result in query_results if result['key'] == course_id), None)
            offers = self._get_offers_for_product(product, voucher, course_info, offers)
        return offers

    def _get_voucher_benefit(self, voucher):
        """
        Retrieves a benefit for the first offer from the specified voucher
        """
        return voucher.offers.first().benefit

    def _get_voucher_catalog_query(self, voucher):
        """
        Retrieves the catalog query, from the range, from the benefit, from the offer, from the specified voucher...
        """
        benefit = self._get_voucher_benefit(voucher)
        return benefit.range.catalog_query

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
        # If a voucher was not provided, return an empty offer set
        if not voucher or not products:
            return []

        # If we are looking up the offers by catalog query, execute the batch workflow
        if self._get_voucher_catalog_query(voucher):
            return self._get_offers_for_catalog_query(request, products, voucher)

        # If we are looking up offers for a specific product, call the individual workflow directly
        else:
            return self._get_offers_for_product(products[0], voucher)
