from django.conf.urls import url, include
from rest_framework_extensions.routers import ExtendedSimpleRouter

from ecommerce.core.constants import COURSE_ID_PATTERN
from ecommerce.extensions.api.v2.views import (
    baskets as basket_views,
    catalog as catalog_views,
    checkout as checkout_views,
    coupons as coupon_views,
    courses as course_views,
    orders as order_views,
    partners as partner_views,
    payments as payment_views,
    products as product_views,
    publication as publication_views,
    refunds as refund_views,
    siteconfiguration as siteconfiguration_views,
    stockrecords as stockrecords_views,
    vouchers as voucher_views
)
from ecommerce.extensions.voucher.views import CouponReportCSVView

ORDER_NUMBER_PATTERN = r'(?P<number>[-\w]+)'
BASKET_ID_PATTERN = r'(?P<basket_id>[\d]+)'

BASKET_URLS = [
    url(r'^$', basket_views.BasketCreateView.as_view(), name='create'),
    url(
        r'^{basket_id}/$'.format(basket_id=BASKET_ID_PATTERN),
        basket_views.BasketDestroyView.as_view(),
        name='destroy'
    ),
    url(
        r'^{basket_id}/order/$'.format(basket_id=BASKET_ID_PATTERN),
        basket_views.OrderByBasketRetrieveView.as_view(),
        name='retrieve_order'
    ),
]

PAYMENT_URLS = [
    url(r'^processors/$', payment_views.PaymentProcessorListView.as_view(),
        name='list_processors'),
]

REFUND_URLS = [
    url(r'^$', refund_views.RefundCreateView.as_view(), name='create'),
    url(r'^(?P<pk>[\d]+)/process/$', refund_views.RefundProcessView.as_view(), name='process'),
]

COUPON_URLS = [
    url(r'^coupon_reports/(?P<coupon_id>[\d]+)/$', CouponReportCSVView.as_view(), name='coupon_reports'),
    url(r'^categories/$', coupon_views.CouponCategoriesListView.as_view(), name='coupons_categories'),
]

CHECKOUT_URLS = [
    url(r'^$', checkout_views.CheckoutView.as_view(), name='process')
]

ATOMIC_PUBLICATION_URLS = [
    url(r'^$', publication_views.AtomicPublicationView.as_view(), name='create'),
    url(
        r'^{course_id}$'.format(course_id=COURSE_ID_PATTERN),
        publication_views.AtomicPublicationView.as_view(),
        name='update'
    ),
]

urlpatterns = [
    url(r'^baskets/', include(BASKET_URLS, namespace='baskets')),
    url(r'^checkout/$', include(CHECKOUT_URLS, namespace='checkout')),
    url(r'^coupons/', include(COUPON_URLS, namespace='coupons')),
    url(r'^payment/', include(PAYMENT_URLS, namespace='payment')),
    url(r'^refunds/', include(REFUND_URLS, namespace='refunds')),
    url(r'^publication/', include(ATOMIC_PUBLICATION_URLS, namespace='publication')),
]

router = ExtendedSimpleRouter()
router.register(r'courses', course_views.CourseViewSet) \
    .register(r'products', product_views.ProductViewSet,
              base_name='course-product', parents_query_lookups=['course_id'])
router.register(r'partners', partner_views.PartnerViewSet) \
    .register(r'products', product_views.ProductViewSet,
              base_name='partner-product', parents_query_lookups=['stockrecords__partner_id'])
router.register(r'partners', partner_views.PartnerViewSet) \
    .register(r'catalogs', catalog_views.CatalogViewSet,
              base_name='partner-catalogs', parents_query_lookups=['partner_id'])
router.register(r'products', product_views.ProductViewSet)
router.register(r'stockrecords', stockrecords_views.StockRecordViewSet, base_name='stockrecords')

router.register(r'catalogs', catalog_views.CatalogViewSet) \
    .register(r'products', product_views.ProductViewSet, base_name='catalog-product',
              parents_query_lookups=['stockrecords__catalogs'])

router.register(r'coupons', coupon_views.CouponViewSet, base_name='coupons')
router.register(r'orders', order_views.OrderViewSet)

router.register(r'vouchers', voucher_views.VoucherViewSet, base_name='vouchers')
router.register(r'siteconfiguration', siteconfiguration_views.SiteConfigurationViewSet, base_name='siteconfiguration')
urlpatterns += router.urls
