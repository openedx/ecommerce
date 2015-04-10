""" Payment-related URLs """
from django.conf.urls import patterns, url

from ecommerce.extensions.payment import views

urlpatterns = patterns(
    '',
    url(r'processors/$', views.ProcessorListView.as_view(), name='processor_list'),
    url(r'/cybersource/callback/$', views.CybersourceResponseView.as_view(), name='cybersource_callback'),
)
