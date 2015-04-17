from django.conf.urls import patterns, url, include

from ecommerce.extensions.app import application
from ecommerce.extensions.payment.app import application as payment


urlpatterns = patterns(
    '',
    url(r'^api/', include('ecommerce.extensions.api.urls', namespace='api')),
    url(r'^payment/', include(payment.urls)),
    url(r'', include(application.urls)),
)
