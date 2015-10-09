"""HTTP endpoints for interacting with vouchers."""
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from extensions.voucher.models import Voucher
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet
from ecommerce.extensions.api import serializers


class VoucherViewSet(NonDestroyableModelViewSet):
    queryset = Voucher.objects.all()
    serializer_class = serializers.VoucherSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)
