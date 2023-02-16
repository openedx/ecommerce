from django.conf.urls import include, url

urlpatterns = [
    url(r'', include('ecommerce.extensions.iap.api.urls')),
]
