from django.conf.urls import url

from ecommerce.extensions.voucher import views

urlpatterns = [
    url(r'^(.*)$', views.VoucherAppView.as_view(), name='app')
]
