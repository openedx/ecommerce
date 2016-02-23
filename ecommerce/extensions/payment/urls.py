""" Payment-related URLs """
from django.conf.urls import url

from ecommerce.extensions.payment.views import PayboxSystemNotifyView

urlpatterns = [
    url(r'^paybox/notify/$', PayboxSystemNotifyView.as_view(), name='paybox_notify'),
    #url(r'^paypal/execute/$', views.PaypalPaymentExecutionView.as_view(), name='paypal_execute'),
    #url(r'^paypal/profiles/$', views.PaypalProfileAdminView.as_view(), name='paypal_profiles'),
]
