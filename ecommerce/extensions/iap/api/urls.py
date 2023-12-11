from django.urls import include, path

urlpatterns = [
    path('v1/', include('ecommerce.extensions.iap.api.v1.urls')),
]
