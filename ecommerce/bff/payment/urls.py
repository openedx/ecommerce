

from django.conf.urls import include, url
from rest_framework.urlpatterns import format_suffix_patterns

from ecommerce.extensions.basket.views import (
    CaptureContextApiView,
    PaymentApiView,
    QuantityAPIView,
    VoucherAddApiView,
    VoucherRemoveApiView
)

PAYMENT_URLS = [
    url(r'^capture-context/$', CaptureContextApiView.as_view(), name='capture_context'),
    url(r'^payment/$', PaymentApiView.as_view(), name='payment'),
    url(r'^quantity/$', QuantityAPIView.as_view(), name='quantity'),
    url(r'^vouchers/$', VoucherAddApiView.as_view(), name='addvoucher'),
    url(r'^vouchers/(?P<voucherid>[\d]+)$', VoucherRemoveApiView.as_view(), name='removevoucher'),
]

urlpatterns = [
    url(r'^v0/', include((PAYMENT_URLS, 'v0'))),
]

urlpatterns = format_suffix_patterns(urlpatterns)
