"""HTTP endpoints for interacting with vouchers."""
import logging

import django_filters
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from rest_framework import filters, status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework_extensions.decorators import action

from ecommerce.courses.models import Course
from ecommerce.coupons.views import get_voucher_from_code
from ecommerce.extensions.api import exceptions, serializers
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
    permission_classes = (IsAuthenticated, IsAdminUser,)
    filter_backends = (filters.DjangoFilterBackend, )
    filter_class = VoucherFilter

    @action(is_for_list=True, methods=['get'], endpoint='offers')
    def offers(self, request):
        """
        Preview the courses offered by the voucher.
        A list of course runs, indicating a course run presence within the catalog, will be returned.
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
            voucher, products = get_voucher_from_code(code)
        except Voucher.DoesNotExist:
            logger.error('Voucher with code %s not found.', code)
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except exceptions.ProductNotFoundError:
            logger.error('No product is associated with code %s.', code)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        offers = self.get_offers(products, request, voucher)
        return Response(data={'offers': offers})

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
        offers = []
        query_results = request.site.siteconfiguration.course_catalog_api_client.course_runs.get(
            q=benefit.range.catalog_query
        )['results']

        for product in products:
            course_catalog_data = next((result for result in query_results if result['key'] == product.course_id), None)

            try:
                course = Course.objects.get(id=product.course_id)
            except Course.DoesNotExist:
                logger.error('Course %s not found.', product.course_id)

            if course_catalog_data and course:
                if benefit.range.catalog:
                    stock_record = benefit.range.catalog.stock_records.get(product__id=product.id)
                else:
                    stock_record = StockRecord.objects.get(product__id=product.id)

                offers.append({
                    'benefit': serializers.BenefitSerializer(benefit).data,
                    'course_start_date': course_catalog_data['start'],
                    'id': course.id,
                    'image_url': course_catalog_data['image']['src'],
                    'organization': CourseKey.from_string(course.id).org,
                    'seat_type': course.type,
                    'stockrecords': serializers.StockRecordSerializer(stock_record).data,
                    'title': course.name,
                    'voucher_end_date': voucher.end_datetime
                })
        return offers
