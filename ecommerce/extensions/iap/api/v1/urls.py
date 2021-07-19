from django.conf.urls import url

from ecommerce.extensions.iap.api.v1.views import MobileBasketAddItemsView, MobileCoursePurchaseExecutionView


urlpatterns = [
    url(r'^basket/add/$', MobileBasketAddItemsView.as_view(), name='mobile-basket-add'),
    url(r'^execute/$', MobileCoursePurchaseExecutionView.as_view(), name='iap-execute'),
]
