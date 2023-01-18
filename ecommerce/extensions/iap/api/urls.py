from django.conf.urls import include, url

urlpatterns = [
    url(r'^v1/', include('ecommerce.extensions.iap.api.v1.urls')),
]
