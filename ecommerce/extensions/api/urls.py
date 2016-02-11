from django.conf.urls import url, include

urlpatterns = [
    url(r'^v2/', include('ecommerce.extensions.api.v2.urls', namespace='v2')),
    url(r'^demo/', include('ecommerce.extensions.api.demo.urls', namespace='demo')),
]
