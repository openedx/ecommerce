""" Payment-related URLs """
from django.conf.urls import url

from ecommerce.payment_processors.paypal import views

urlpatterns = [
    url(r'^paypal/execute/$', views.PaypalPaymentExecutionView.as_view(), name='paypal_execute'),
    url(r'^paypal/profiles/$', views.PaypalProfileAdminView.as_view(), name='paypal_profiles'),
]
