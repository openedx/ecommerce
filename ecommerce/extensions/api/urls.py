from django.conf.urls import patterns, url, include

from ecommerce.extensions.api import views


ORDER_NUMBER_PATTERN = r"(?P<number>[-\w]+)"
BASKET_ID_PATTERN = r"(?P<basket_id>[\w]+)"

ORDER_URLS = patterns(
    '',
    url(r'^$', views.OrderListCreateAPIView.as_view(), name='create_list'),
    url(
        r'^{number}/$'.format(number=ORDER_NUMBER_PATTERN),
        views.RetrieveOrderView.as_view(),
        name='retrieve'
    ),
    url(
        r'^{number}/fulfill/$'.format(number=ORDER_NUMBER_PATTERN),
        views.FulfillOrderView.as_view(),
        name='fulfill'
    ),
)

urlpatterns = patterns(
    '',
    url(r'^processors/$', views.PaymentProcessorsView.as_view(), name='payment_processors'),
    url(r'^orders/', include(ORDER_URLS, namespace='orders')),
    url(
        r'^baskets/{basket_id}/order/$'.format(basket_id=BASKET_ID_PATTERN),
        views.RetrieveOrderByBasketView.as_view(),
        name='order_by_basket'
    ),
)
