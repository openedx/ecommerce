"""HTTP endpoints for interacting with products."""

import logging

from django.db.models import Q
from oscar.core.loading import get_model
from rest_framework import filters
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin

from ecommerce.core.constants import COURSE_ENTITLEMENT_CLASS_NAME

from ecommerce.entitlements.utils import create_or_update_course_entitlement

from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.filters import ProductFilter
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet


logger = logging.getLogger(__name__)
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

        product_class = request.data['product_class']
        partner = request.site.siteconfiguration.partner

        if product_class == COURSE_ENTITLEMENT_CLASS_NAME:
            logger.info('Creating new Course ENtitlement')
            price = request.data['price']
            name = request.data['title']
            product_attrs = request.data['attribute_values']
            for attr in product_attrs:
                if attr['name'] == 'certificate_type':
                    certificate_type = attr['value']
                elif attr['name'] == 'course_key':
                    course_id = attr['value']
            create_or_update_course_entitlement(certificate_type, price, partner, course_id, name)

        return Response()
