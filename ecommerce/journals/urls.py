from django.conf.urls import include, url

from ecommerce.journals import views

OFFER_URLS = [
    url(r'^$', views.JournalBundleOfferListView.as_view(), name='list'),
    url(r'new/$', views.JournalBundleOfferCreateView.as_view(), name='new'),
    url(r'^(?P<pk>[\d]+)/edit/$', views.JournalBundleOfferUpdateView.as_view(), name='edit'),
]

urlpatterns = [
    url(r'^offers/', include(OFFER_URLS, namespace='offers')),
    url(r'^api/', include('ecommerce.journals.api.urls', namespace='api')),
]
