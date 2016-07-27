from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from ecommerce.core.models import BusinessClient
from ecommerce.extensions.api import serializers


class ClientViewSet(viewsets.ModelViewSet):
    queryset = BusinessClient.objects.all()
    serializer_class = serializers.BusinessClientSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)
