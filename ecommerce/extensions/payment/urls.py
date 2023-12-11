

from django.conf import settings
from django.urls import include, path, re_path

from ecommerce.extensions.payment.views import PaymentFailedView, cybersource, paypal, stripe
from ecommerce.extensions.payment.views.sdn import SDNCheckFailureView, SDNCheckView, SDNFailure

CYBERSOURCE_APPLE_PAY_URLS = [
    path('authorize/', cybersource.CybersourceApplePayAuthorizationView.as_view(), name='authorize'),
    path('start-session/', cybersource.ApplePayStartSessionView.as_view(), name='start_session'),
]
CYBERSOURCE_URLS = [
    path('apple-pay/', include((CYBERSOURCE_APPLE_PAY_URLS, 'apple_pay'))),
    path('authorize/', cybersource.CybersourceAuthorizeAPIView.as_view(), name='authorize'),
]

PAYPAL_URLS = [
    path('execute/', paypal.PaypalPaymentExecutionView.as_view(), name='execute'),
    path('profiles/', paypal.PaypalProfileAdminView.as_view(), name='profiles'),
]

SDN_URLS = [
    path('check/', SDNCheckView.as_view(), name='check'),
    path('failure/', SDNFailure.as_view(), name='failure'),
    path('metadata/', SDNCheckFailureView.as_view(), name='metadata'),
]

STRIPE_URLS = [
    path('submit/', stripe.StripeSubmitView.as_view(), name='submit'),
    re_path(r'^checkout', stripe.StripeCheckoutView.as_view(), name='checkout'),
]

urlpatterns = [
    path('cybersource/', include((CYBERSOURCE_URLS, 'cybersource'))),
    path('error/', PaymentFailedView.as_view(), name='payment_error'),
    path('paypal/', include((PAYPAL_URLS, 'paypal'))),
    path('sdn/', include((SDN_URLS, 'sdn'))),
    path('stripe/', include((STRIPE_URLS, 'stripe'))),
]

for payment_processor_name, urls_module in settings.EXTRA_PAYMENT_PROCESSOR_URLS.items():
    processor_url = re_path(r'^{}/'.format(payment_processor_name), include((urls_module, payment_processor_name)))
    urlpatterns.append(processor_url)
