"""HTTP endpoints for interacting with vouchers."""
from oscar.core.loading import get_model
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from ecommerce.extensions.api import serializers


Voucher = get_model('voucher', 'Voucher')


class VoucherViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Voucher.objects.all()
    serializer_class = serializers.VoucherSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)
