from django.conf.urls import include, url

from ecommerce.journal import views

OFFER_URLS = [
    url(r'^$', views.JournalOfferListView.as_view(), name='list'),
    url(r'new/$', views.JournalOfferCreateView.as_view(), name='new'),
    url(r'^(?P<pk>[\d]+)/edit/$', views.JournalOfferUpdateView.as_view(), name='edit'),
]

urlpatterns = [
    url(r'^offers/', include(OFFER_URLS, namespace='offers')),
    url(r'^api/', include('ecommerce.journal.api.urls', namespace='api')),
]
