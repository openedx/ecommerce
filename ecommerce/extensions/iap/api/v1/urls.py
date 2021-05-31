from django.conf.urls import url

from ecommerce.extensions.iap.api.v1.views import MobileBasketAddItemsView


urlpatterns = [
    url(r'^basket/add/$', MobileBasketAddItemsView.as_view(), name='mobile-basket-add'),
]
