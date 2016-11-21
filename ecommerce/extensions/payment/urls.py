""" Payment-related URLs """
from django.conf.urls import url

from ecommerce.extensions.payment.views.cybersource import CybersourceNotifyView, CybersourceSubmitView
from ecommerce.extensions.payment.views.paypal import PaypalPaymentExecutionView, PaypalProfileAdminView

urlpatterns = [
    url(r'^cybersource/notify/$', CybersourceNotifyView.as_view(), name='cybersource_notify'),
    url(r'^cybersource/submit/$', CybersourceSubmitView.as_view(), name='cybersource_submit'),
    url(r'^paypal/execute/$', PaypalPaymentExecutionView.as_view(), name='paypal_execute'),
    url(r'^paypal/profiles/$', PaypalProfileAdminView.as_view(), name='paypal_profiles'),
]
