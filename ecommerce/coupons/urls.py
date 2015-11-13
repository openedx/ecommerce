from django.conf.urls import url

from ecommerce.coupons import views

urlpatterns = [
    url(r'^(.*)$', views.CouponAppView.as_view(), name='app'),
]
