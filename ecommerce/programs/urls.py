

from django.conf.urls import include, url

from ecommerce.programs import views

OFFER_URLS = [
    url(r'^$', views.ProgramOfferListView.as_view(), name='list'),
    url(r'^new/$', views.ProgramOfferCreateView.as_view(), name='new'),
    url(r'^(?P<pk>[\d]+)/edit/$', views.ProgramOfferUpdateView.as_view(), name='edit'),
]
urlpatterns = [

    url(r'^offers/', include((OFFER_URLS, 'offers'))),
]
