

from django.apps import apps
from django.conf import settings
from django.conf.urls import include, url

payment = apps.get_app_config('payment')
application = apps.get_app_config('ecommerce')

urlpatterns = [
    url(r'^api/', include(('ecommerce.extensions.api.urls', 'api'))),
    url(r'^api/iap/', include(('ecommerce.extensions.iap.urls', 'iap'))),
    url(r'^payment/', include(payment.urls[0])),
    url(r'', include(application.urls[0])),
]

if getattr(settings, 'ENABLE_EXECUTIVE_EDUCATION_2U_FULFILLMENT', False):
    urlpatterns.append(
        url(
            r'^executive-education-2u/',
            include(('ecommerce.extensions.executive_education_2u.urls', 'executive_education_2u'))
        )
    )
