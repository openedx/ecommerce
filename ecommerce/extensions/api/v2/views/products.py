"""HTTP endpoints for interacting with products."""
from django.db.models import Q
from oscar.core.loading import get_model
from rest_framework import filters
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework_extensions.mixins import NestedViewSetMixin

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
        #   - course partner: for products that don't have a stockrecord (parent course)
        partner = self.request.site.siteconfiguration.partner
        return super(ProductViewSet, self).get_queryset().filter(
            Q(stockrecords__partner=partner) |
            Q(course__partner=partner)
        )
