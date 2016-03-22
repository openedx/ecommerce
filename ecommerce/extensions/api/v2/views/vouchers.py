"""HTTP endpoints for interacting with vouchers."""
import django_filters
from oscar.core.loading import get_model
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.v2.views import NonDestroyableModelViewSet


Voucher = get_model('voucher', 'Voucher')


class VoucherFilter(django_filters.FilterSet):
    """
    Filter for vouchers via query string parameters.
    Currently supports filtering via the voucher's code.
    """
    code = django_filters.CharFilter(name='code', lookup_type='exact')

    class Meta(object):
        model = Voucher
        fields = ('code', )


class VoucherViewSet(NonDestroyableModelViewSet):
    """ View set for vouchers. """
    queryset = Voucher.objects.all()
    serializer_class = serializers.VoucherSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)
    filter_backends = (filters.DjangoFilterBackend, )
    filter_class = VoucherFilter
