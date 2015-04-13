from django.conf.urls import patterns, url, include

from ecommerce.extensions.app import application
from ecommerce.extensions.payment.app import application as payment


urlpatterns = patterns(
    '',
    # Oscar URLs
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^api/', include('ecommerce.extensions.api.urls', namespace='api')),
    url(r'^payment/', include(payment.urls)),

    # This is only here to ensure the login page works for integration tests.
    url(r'^dummy/', lambda r: r, name='password-reset'),

    url(r'', include(application.urls)),
)
