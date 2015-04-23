from django.conf.urls import patterns, url, include
from django.views.decorators.cache import cache_page

from ecommerce.extensions.api.v2 import views


ORDER_NUMBER_PATTERN = r'(?P<number>[-\w]+)'
BASKET_ID_PATTERN = r'(?P<basket_id>[\w]+)'

BASKET_URLS = patterns(
    '',
    url(r'^$', views.BasketCreateView.as_view(), name='create'),
    url(
        r'^{basket_id}/order/$'.format(basket_id=BASKET_ID_PATTERN),
        views.OrderByBasketRetrieveView.as_view(),
        name='retrieve_order'
    ),
)

ORDER_URLS = patterns(
    '',
    url(r'^$', views.OrderListView.as_view(), name='list'),
    url(
        r'^{number}/$'.format(number=ORDER_NUMBER_PATTERN),
        views.OrderRetrieveView.as_view(),
        name='retrieve'
    ),
    url(
        r'^{number}/fulfill/$'.format(number=ORDER_NUMBER_PATTERN),
        views.OrderFulfillView.as_view(),
        name='fulfill'
    ),
)

PAYMENT_URLS = patterns(
    '',
    url(r'^processors/$', cache_page(60 * 30)(views.PaymentProcessorListView.as_view()), name='list_processors'),
)

urlpatterns = patterns(
    '',
    url(r'^baskets/', include(BASKET_URLS, namespace='baskets')),
    url(r'^orders/', include(ORDER_URLS, namespace='orders')),
    url(r'^payment/', include(PAYMENT_URLS, namespace='payment')),
)
