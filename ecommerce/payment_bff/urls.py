from django.conf.urls import include, url
from rest_framework.urlpatterns import format_suffix_patterns

from ecommerce.extensions.basket.views import AddVoucherApiView, PaymentApiView, RemoveVoucherApiView

PAYMENT_URLS = [
    url(r'^$', PaymentApiView.as_view(), name='payment'),
    url(r'^vouchers/$', AddVoucherApiView.as_view(), name='addvoucher'),
    url(r'^vouchers/(?P<voucherid>[\d]+)$', RemoveVoucherApiView.as_view(), name='removevoucher'),
]

PAYMENT_ROOT_URL = [
    url(r'^payment/', include(PAYMENT_URLS, namespace='payment')),
]

urlpatterns = [
    url(r'^v0/', include(PAYMENT_ROOT_URL, namespace='v0')),
]

urlpatterns = format_suffix_patterns(urlpatterns)
