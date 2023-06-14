from django.conf.urls import url

from ecommerce.extensions.iap.api.v1.views import (
    AndroidRefundView,
    IOSRefundView,
    MobileBasketAddItemsView,
    MobileCheckoutView,
    MobileCoursePurchaseExecutionView
)

urlpatterns = [
    url(r'^basket/add/$', MobileBasketAddItemsView.as_view(), name='mobile-basket-add'),
    url(r'^checkout/$', MobileCheckoutView.as_view(), name='iap-checkout'),
    url(r'^execute/$', MobileCoursePurchaseExecutionView.as_view(), name='iap-execute'),
    url(r'^android/refund/$', AndroidRefundView.as_view(), name='android-refund'),
    url(r'^ios/refund/$', IOSRefundView.as_view(), name='ios-refund'),
]
