from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from ecommerce.core.models import BusinessClient
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.filters import ClientFilter


class ClientViewSet(viewsets.ModelViewSet):
    queryset = BusinessClient.objects.all()
    serializer_class = serializers.BusinessClientSerializer
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = ClientFilter
    permission_classes = (IsAuthenticated, IsAdminUser,)
