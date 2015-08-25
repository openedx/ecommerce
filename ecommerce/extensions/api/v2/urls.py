from django.conf.urls import url, include
from django.views.decorators.cache import cache_page
from rest_framework_extensions.routers import ExtendedSimpleRouter

from ecommerce.core.constants import COURSE_ID_PATTERN
from ecommerce.extensions.api.v2 import views

ORDER_NUMBER_PATTERN = r'(?P<number>[-\w]+)'
BASKET_ID_PATTERN = r'(?P<basket_id>[\w]+)'

BASKET_URLS = [
    url(r'^$', views.BasketCreateView.as_view(), name='create'),
    url(
        r'^{basket_id}/order/$'.format(basket_id=BASKET_ID_PATTERN),
        views.OrderByBasketRetrieveView.as_view(),
        name='retrieve_order'
    ),
]

ORDER_URLS = [
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
]

PAYMENT_URLS = [
    url(r'^processors/$', cache_page(60 * 30)(views.PaymentProcessorListView.as_view()), name='list_processors'),
]

REFUND_URLS = [
    url(r'^$', views.RefundCreateView.as_view(), name='create'),
    url(r'^(?P<pk>[\d]+)/process/$', views.RefundProcessView.as_view(), name='process'),
]

ATOMIC_PUBLICATION_URLS = [
    url(r'^$', views.AtomicPublicationView.as_view(), name='create'),
    url(
        r'^{course_id}$'.format(course_id=COURSE_ID_PATTERN),
        views.AtomicPublicationView.as_view(),
        name='update'
    ),
]

urlpatterns = [
    url(r'^baskets/', include(BASKET_URLS, namespace='baskets')),
    url(r'^orders/', include(ORDER_URLS, namespace='orders')),
    url(r'^payment/', include(PAYMENT_URLS, namespace='payment')),
    url(r'^refunds/', include(REFUND_URLS, namespace='refunds')),
    url(r'^publication/', include(ATOMIC_PUBLICATION_URLS, namespace='publication')),
]

router = ExtendedSimpleRouter()
router.register(r'courses', views.CourseViewSet) \
    .register(r'products', views.ProductViewSet, base_name='course-product', parents_query_lookups=['course_id'])
router.register(r'products', views.ProductViewSet)

urlpatterns += router.urls
