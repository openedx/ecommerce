"""HTTP endpoints for interacting with products."""
from django.db.models import Q
from django.http import HttpResponseBadRequest
from oscar.core.loading import get_model
from rest_framework import filters, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.filters import ProductFilter
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet

Product = get_model('catalogue', 'Product')


class ProductViewSet(NestedViewSetMixin, NonDestroyableModelViewSet):
    serializer_class = serializers.ProductSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = ProductFilter
    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get_queryset(self):
        self.queryset = Product.objects.all()
        # We are calling the super's .get_queryset() in case of nested
        # products so that they are propery filtered by parent ID first.
        # Products are then filtered by:
        #   - stockrecord partner: for products that have stockrecords (seats, coupons, ...)
        #   - course site: for products that don't have a stockrecord (parent course)
        return super(ProductViewSet, self).get_queryset().filter(
            Q(stockrecords__partner=self.request.site.siteconfiguration.partner) |
            Q(course__site=self.request.site)
        )

    def create(self, request, *args, **kwargs):
        product_class = request.data.get('product_class')
        if product_class == COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME:

            product_creation_fields = {
                'partner': request.site.siteconfiguration.partner,
                'name': request.data.get('title'),
                'price': request.data.get('price'),
                'certificate_type': self._fetch_value_from_attribute_values('certificate_type'),
                'UUID': self._fetch_value_from_attribute_values('UUID')
            }

            for attribute_name, attribute_value in product_creation_fields.items():
                if attribute_value is None:
                    bad_rqst = 'Missing or bad value for: {}, required for Entitlement creation.'.format(attribute_name)
                    return HttpResponseBadRequest(bad_rqst)

            entitlement = create_or_update_course_entitlement(
                product_creation_fields['certificate_type'],
                product_creation_fields['price'],
                product_creation_fields['partner'],
                product_creation_fields['UUID'],
                product_creation_fields['name']
            )

            data = self.serializer_class(entitlement, context={'request': request}).data
            return Response(data, status=status.HTTP_201_CREATED)
        else:
            bad_rqst = "Product API only supports POST for {} products".format(COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)
            return HttpResponseBadRequest(bad_rqst)

    def _fetch_value_from_attribute_values(self, attribute_name):
        attributes = {attribute.get('name'): attribute.get('value') for attribute in self.request.data.get('attribute_values')}  # pylint: disable=line-too-long
        val = attributes.get(attribute_name)
        return val
