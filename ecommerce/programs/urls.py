

from django.urls import include, path, re_path

from ecommerce.programs import views

OFFER_URLS = [
    path('', views.ProgramOfferListView.as_view(), name='list'),
    path('new/', views.ProgramOfferCreateView.as_view(), name='new'),
    re_path(r'^(?P<pk>[\d]+)/edit/$', views.ProgramOfferUpdateView.as_view(), name='edit'),
]
urlpatterns = [

    path('offers/', include((OFFER_URLS, 'offers'))),
]
