from __future__ import absolute_import

from django.apps import apps
from django.conf.urls import include, url

payment = apps.get_app_config('payment')
application = apps.get_app_config('ecommerce')

urlpatterns = [
    url(r'^api/', include(('ecommerce.extensions.api.urls', 'api'))),
    url(r'^payment/', payment.urls),
    url(r'', application.urls),
]
