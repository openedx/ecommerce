"""HTTP endpoints for interacting with products."""
import django_filters
from oscar.core.loading import get_model
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_extensions.mixins import NestedViewSetMixin

from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet


Product = get_model('catalogue', 'Product')


class ProductFilter(django_filters.FilterSet):
    """
    Filter for products via query string parameters.
    Example:
        /api/v2/products/?product_class=coupon
    """
    product_class = django_filters.CharFilter(name='product_class__name', lookup_type='iexact')

    class Meta(object):
        model = Product
        fields = ('product_class',)


class ProductViewSet(NestedViewSetMixin, NonDestroyableModelViewSet):
    queryset = Product.objects.all()
    serializer_class = serializers.ProductSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = ProductFilter
    permission_classes = (IsAuthenticated, IsAdminUser,)
