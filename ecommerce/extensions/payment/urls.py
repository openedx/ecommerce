""" Payment-related URLs """
from django.conf.urls import patterns, url

from ecommerce.extensions.payment import views

urlpatterns = patterns(
    '',
    url(r'^cybersource/notify/$', views.CybersourceNotifyView.as_view(), name='cybersource_notify'),
    url(r'^paypal/execute/$', views.PaypalPaymentExecutionView.as_view(), name='paypal_execute'),
)
