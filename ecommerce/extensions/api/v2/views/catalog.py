from oscar.core.loading import get_model
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_extensions.mixins import NestedViewSetMixin

from ecommerce.extensions.api import serializers


Catalog = get_model('catalogue', 'Catalog')


class CatalogViewSet(NestedViewSetMixin, ReadOnlyModelViewSet):
    queryset = Catalog.objects.all()
    serializer_class = serializers.CatalogSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)
