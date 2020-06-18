

from django.conf.urls import include, url

urlpatterns = [
    url(r'^v2/', include(('ecommerce.extensions.api.v2.urls', 'v2'))),
]
