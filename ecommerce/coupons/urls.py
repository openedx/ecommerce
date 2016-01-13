from django.conf.urls import url

from ecommerce.coupons import views

urlpatterns = [
    url(r'^offer/$', views.CouponOfferView.as_view(), name='offer'),
    url(r'^redeem/$', views.CouponRedeemView.as_view(), name='redeem'),
    url(r'^(.*)$', views.CouponAppView.as_view(), name='app'),
]
