

from django.urls import include, path

urlpatterns = [
    path('v2/', include(('ecommerce.extensions.api.v2.urls', 'v2'))),
]
