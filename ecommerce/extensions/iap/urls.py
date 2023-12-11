from django.urls import include, path

urlpatterns = [
    path('', include('ecommerce.extensions.iap.api.urls')),
]
