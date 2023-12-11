from django.urls import path

from ecommerce.extensions.iap.api.v1.views import (
    AndroidRefundView,
    IOSRefundView,
    MobileBasketAddItemsView,
    MobileCheckoutView,
    MobileCoursePurchaseExecutionView
)

urlpatterns = [
    path('basket/add/', MobileBasketAddItemsView.as_view(), name='mobile-basket-add'),
    path('checkout/', MobileCheckoutView.as_view(), name='iap-checkout'),
    path('execute/', MobileCoursePurchaseExecutionView.as_view(), name='iap-execute'),
    path('android/refund/', AndroidRefundView.as_view(), name='android-refund'),
    path('ios/refund/', IOSRefundView.as_view(), name='ios-refund'),
]
