

from django.urls import include, path, re_path

from ecommerce.enterprise import views

OFFER_URLS = [
    path('', views.EnterpriseOfferListView.as_view(), name='list'),
    path('new/', views.EnterpriseOfferCreateView.as_view(), name='new'),
    re_path(r'^(?P<pk>[\d]+)/edit/$', views.EnterpriseOfferUpdateView.as_view(), name='edit'),
]

urlpatterns = [
    path('offers/', include((OFFER_URLS, 'offers'))),
    re_path(r'^coupons/(.*)$', views.EnterpriseCouponAppView.as_view(), name='coupons'),
]
