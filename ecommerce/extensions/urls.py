

from django.apps import apps
from django.conf import settings
from django.urls import include, path

payment = apps.get_app_config('payment')
application = apps.get_app_config('ecommerce')

urlpatterns = [
    path('api/', include(('ecommerce.extensions.api.urls', 'api'))),
    path('api/iap/', include(('ecommerce.extensions.iap.urls', 'iap'))),
    path('payment/', include(payment.urls[0])),
    path('', include(application.urls[0])),
]

if getattr(settings, 'ENABLE_EXECUTIVE_EDUCATION_2U_FULFILLMENT', False):
    urlpatterns.append(
        path(
            'executive-education-2u/',
            include(('ecommerce.extensions.executive_education_2u.urls', 'executive_education_2u'))
        )
    )
