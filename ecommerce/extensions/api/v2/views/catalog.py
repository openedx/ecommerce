import logging

from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_extensions.decorators import action
from rest_framework_extensions.mixins import NestedViewSetMixin
from slumber.exceptions import SlumberBaseException

from ecommerce.core.constants import DEFAULT_CATALOG_PAGE_SIZE
from ecommerce.coupons.utils import get_range_catalog_query_results
from ecommerce.extensions.api import serializers


Catalog = get_model('catalogue', 'Catalog')
Product = get_model('catalogue', 'Product')
logger = logging.getLogger(__name__)


class CatalogViewSet(NestedViewSetMixin, ReadOnlyModelViewSet):
    queryset = Catalog.objects.all()
    serializer_class = serializers.CatalogSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)

    @action(is_for_list=True, methods=['get'])
    def preview(self, request):
        """
        Preview the results of the catalog query.
        A list of course runs, indicating a course run presence within the catalog, will be returned.
        ---
        parameters:
            - name: query
              description: Elasticsearch querystring query
              required: true
              type: string
              paramType: query
              multiple: false
        """
        query = request.GET.get('query')
        seat_types = request.GET.get('seat_types')
        offset = request.GET.get('offset')
        limit = request.GET.get('limit', DEFAULT_CATALOG_PAGE_SIZE)

        if query and seat_types:
            seat_types = seat_types.split(',')
            try:
                response = get_range_catalog_query_results(
                    limit=limit,
                    query=query,
                    site=request.site,
                    offset=offset
                )
                results = response['results']
                course_ids = [result['key'] for result in results]
                seats = serializers.ProductSerializer(
                    Product.objects.filter(
                        course_id__in=course_ids,
                        attributes__name='certificate_type',
                        attribute_values__value_text__in=seat_types
                    ),
                    many=True,
                    context={'request': request}
                ).data
                data = {
                    'next': response['next'],
                    'seats': seats
                }
                return Response(data=data)
            except (ConnectionError, SlumberBaseException, Timeout):
                logger.error('Unable to connect to Course Catalog service.')
                return Response(status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_400_BAD_REQUEST)
