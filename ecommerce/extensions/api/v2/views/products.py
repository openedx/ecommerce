"""HTTP endpoints for interacting with products."""


import logging

import django_filters
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.filters import ProductFilter
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet

logger = logging.getLogger(__name__)

Product = get_model('catalogue', 'Product')


class ProductViewSet(NestedViewSetMixin, NonDestroyableModelViewSet):
    serializer_class = serializers.ProductSerializer
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = ProductFilter
    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get_queryset(self):
        self.queryset = Product.objects.all()
        # We are calling the super's .get_queryset() in case of nested
        # products so that they are propery filtered by parent ID first.
        # Products are then filtered by:
        #   - stockrecord partner: for products that have stockrecords (seats, coupons, ...)
        #   - course partner: for products that don't have a stockrecord (parent course)
        partner = self.request.site.siteconfiguration.partner
        return super(ProductViewSet, self).get_queryset().filter(
            Q(stockrecords__partner=partner) |
            Q(course__partner=partner)
        )

    def invalid_product_response(self, http_method):
        """
        Constructs a Response for an invalid product for a given http method.

        Parameters:
            http_method (str): The http_method being attempted
        Returns:
            Response: Response with a message explaining the issue and a 400 status.
        """
        bad_request_message = _('Product API only supports {http_method} for {product_class} products.').format(
            http_method=http_method, product_class=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
        )
        logger.error(bad_request_message)
        return Response(bad_request_message, status=status.HTTP_400_BAD_REQUEST)

    def missing_values_response(self, missing_values):
        """
        Constructs a Response for missing values from the request.

        Parameters:
            missing_values (list of str): contains the names of the fields that are missing values.
        Returns:
            Response: Response with a message explaining the issue and a 400 status.
        """
        bad_request_message = [_('Missing or bad value for: [{name}].').format(name=name) for name in missing_values]
        bad_request_message = ' '.join(bad_request_message)
        logger.error(bad_request_message)
        return Response(bad_request_message, status=status.HTTP_400_BAD_REQUEST)

    def create(self, request, *args, **kwargs):
        """ Create a Product """
        data = request.data
        if data.get('product_class') == COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME:
            product_creation_fields = {
                'certificate_type': data.get('certificate_type'),
                'price': data.get('price'),
                'partner': request.site.siteconfiguration.partner,
                'UUID': data.get('uuid'),
                'title': data.get('title'),
            }

            missing_values = [k for k, v in sorted(list(product_creation_fields.items())) if v is None]
            if missing_values:
                return self.missing_values_response(missing_values)
            entitlement = create_or_update_course_entitlement(**product_creation_fields)

            entitlement_data = self.serializer_class(entitlement, context={'request': request}).data
            return Response(entitlement_data, status=status.HTTP_201_CREATED)
        return self.invalid_product_response('POST')
