from django.conf.urls import include, url

from ecommerce.digital_books import views

OFFER_URLS = [
    url(r'^$', views.DigitalBookOfferListView.as_view(), name='list'),
    url(r'^new/$', views.DigitalBookOfferCreateView.as_view(), name='new')
]

urlpatterns = [
    url(r'^offers/', include(OFFER_URLS, namespace='offers')),
]