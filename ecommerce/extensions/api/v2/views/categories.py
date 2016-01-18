"""HTTP endpoints for interacting with categories."""
import django_filters
from oscar.core.loading import get_model
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from ecommerce.extensions.api import serializers


Category = get_model('catalogue', 'Category')


class CategoryFilter(django_filters.FilterSet):
    """Filter for categories via query string parameters."""
    depth = django_filters.NumberFilter(name='depth', lookup_type='exact')
    path = django_filters.CharFilter(name='path', lookup_type='startswith')

    class Meta(object):
        model = Category
        fields = ('depth', 'path')


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = serializers.CategorySerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = CategoryFilter
    permission_classes = (IsAuthenticated, IsAdminUser,)
