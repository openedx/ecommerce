

from django.apps import apps
from django.urls import include, path

payment = apps.get_app_config('payment')
application = apps.get_app_config('ecommerce')

urlpatterns = [
    path('api/', include(('ecommerce.extensions.api.urls', 'api'))),
    path('payment/', include(payment.urls[0])),
    path('', include(application.urls[0])),
]
