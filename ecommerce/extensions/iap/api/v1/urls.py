from django.conf.urls import url

from ecommerce.extensions.iap.api.v1.views import (
    AndroidRefund,
    MobileBasketAddItemsView,
    MobileCheckoutView,
    MobileCoursePurchaseExecutionView
)

urlpatterns = [
    url(r'^basket/add/$', MobileBasketAddItemsView.as_view(), name='mobile-basket-add'),
    url(r'^execute/$', MobileCoursePurchaseExecutionView.as_view(), name='iap-execute'),
    url(r'^checkout/$', MobileCheckoutView.as_view(), name='iap-checkout'),
    url(r'^android/refund/$', AndroidRefund.as_view(), name='android-refund')
]
