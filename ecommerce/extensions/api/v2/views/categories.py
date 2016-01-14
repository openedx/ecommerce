"""HTTP endpoints for interacting with categories."""
from oscar.core.loading import get_model
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from ecommerce.extensions.api import serializers


Category = get_model('catalogue', 'Category')


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = serializers.CategorySerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)
