from __future__ import absolute_import

from django.conf.urls import include, url

from ecommerce.extensions.app import application
from ecommerce.extensions.payment.app import application as payment

urlpatterns = [
    url(r'^api/', include(('ecommerce.extensions.api.urls', 'api'))),
    url(r'^payment/', payment.urls),
    url(r'', application.urls),
]
