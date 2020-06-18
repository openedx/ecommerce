

import logging

from oscar.core.loading import get_model
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_extensions.mixins import NestedViewSetMixin
from slumber.exceptions import SlumberBaseException

from ecommerce.core.constants import DEFAULT_CATALOG_PAGE_SIZE
from ecommerce.coupons.utils import get_catalog_course_runs
from ecommerce.courses.utils import get_course_catalogs
from ecommerce.extensions.api import serializers

Catalog = get_model('catalogue', 'Catalog')
Product = get_model('catalogue', 'Product')
logger = logging.getLogger(__name__)


class CatalogViewSet(NestedViewSetMixin, ReadOnlyModelViewSet):
    serializer_class = serializers.CatalogSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get_queryset(self):
        self.queryset = Catalog.objects.all()
        # We are calling the super's .get_queryset() in case of nested
        # catalogs so that they are propery filtered by parent ID first.
        return super(CatalogViewSet, self).get_queryset().filter(
            partner=self.request.site.siteconfiguration.partner
        )

    @action(detail=False)
    def preview(self, request):
        """ Preview the results of the catalog query.

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

        if not (query and seat_types):
            detail = {}

            if not query:
                detail['query'] = 'The query parameter is required.'

            if not seat_types:
                detail['seat_types'] = 'The seat_type parameter is required.'

            raise ValidationError(detail=detail)

        seat_types = seat_types.split(',')

        try:
            response = get_catalog_course_runs(
                site=request.site,
                query=query,
                limit=limit,
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
        except (ReqConnectionError, SlumberBaseException, Timeout):
            logger.error('Unable to connect to Catalog API.')
            return Response(status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False)
    def course_catalogs(self, request):
        """
        Returns response with all course catalogs in the format:
        ["results": {"id": 1, "name": "Dummy Catalog"}]
        """
        try:
            results = get_course_catalogs(site=request.site)
        except:  # pylint: disable=bare-except
            logger.exception('Failed to retrieve course catalogs data from the Discovery Service API.')
            results = []

        # Create catalogs list with sorting by name
        catalogs = [{'id': catalog['id'], 'name': catalog['name']} for catalog in results]
        data = {'results': sorted(catalogs, key=lambda catalog: catalog.get('name', '').lower())}
        return Response(data=data)
