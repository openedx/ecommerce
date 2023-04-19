

from django.urls import path

from ecommerce.bff.subscriptions.views import ProductEntitlementInfoView

urlpatterns = [
    path('product-entitlement-info/', ProductEntitlementInfoView.as_view(), name='product-entitlement-info'),
]
