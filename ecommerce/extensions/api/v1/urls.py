from django.conf.urls import patterns, url, include

from ecommerce.extensions.api.v1 import views


ORDER_NUMBER_PATTERN = r'(?P<number>[-\w]+)'

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
        views.OrderFulfillView.as_view(),
        name='fulfill'
    ),
)

urlpatterns = patterns(
    '',
    url(r'^orders/', include(ORDER_URLS, namespace='orders'))
)
