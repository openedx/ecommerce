from django.conf.urls import include, url

from ecommerce.extensions.payment.views import PaymentFailedView, SDNFailure, cybersource, paypal

CYBERSOURCE_URLS = [
    url(r'^notify/$', cybersource.CybersourceNotifyView.as_view(), name='notify'),
    url(r'^redirect/$', cybersource.CybersourceInterstitialView.as_view(), name='redirect'),
    url(r'^submit/$', cybersource.CybersourceSubmitView.as_view(), name='submit'),
]

PAYPAL_URLS = [
    url(r'^execute/$', paypal.PaypalPaymentExecutionView.as_view(), name='execute'),
    url(r'^profiles/$', paypal.PaypalProfileAdminView.as_view(), name='profiles'),
    url(r'^webhook/$', paypal.PaypalWebhookView.as_view(), name='webhook'),
]

SDN_URLS = [
    url(r'^failure/$', SDNFailure.as_view(), name='failure'),
]

urlpatterns = [
    url(r'^cybersource/', include(CYBERSOURCE_URLS, namespace='cybersource')),
    url(r'^error/$', PaymentFailedView.as_view(), name='payment_error'),
    url(r'^paypal/', include(PAYPAL_URLS, namespace='paypal')),
    url(r'^sdn/', include(SDN_URLS, namespace='sdn')),
]
