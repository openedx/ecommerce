

from django.urls import include, path, re_path
from rest_framework.urlpatterns import format_suffix_patterns

from ecommerce.extensions.basket.views import (
    CaptureContextApiView,
    PaymentApiView,
    QuantityAPIView,
    VoucherAddApiView,
    VoucherRemoveApiView
)

PAYMENT_URLS = [
    path('capture-context/', CaptureContextApiView.as_view(), name='capture_context'),
    path('payment/', PaymentApiView.as_view(), name='payment'),
    path('quantity/', QuantityAPIView.as_view(), name='quantity'),
    path('vouchers/', VoucherAddApiView.as_view(), name='addvoucher'),
    re_path(r'^vouchers/(?P<voucherid>[\d]+)$', VoucherRemoveApiView.as_view(), name='removevoucher'),
]

urlpatterns = [
    path('v0/', include((PAYMENT_URLS, 'v0'))),
]

urlpatterns = format_suffix_patterns(urlpatterns)
