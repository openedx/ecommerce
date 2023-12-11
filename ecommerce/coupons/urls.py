

from django.urls import path, re_path

from ecommerce.coupons import views

urlpatterns = [
    path('offer/', views.CouponOfferView.as_view(), name='offer'),
    path('redeem/', views.CouponRedeemView.as_view(), name='redeem'),
    re_path(
        r'^enrollment_code_csv/(?P<number>[-\w]+)/$',
        views.EnrollmentCodeCsvView.as_view(),
        name='enrollment_code_csv'
    ),
    re_path(r'^(.*)$', views.CouponAppView.as_view(), name='app'),
]
