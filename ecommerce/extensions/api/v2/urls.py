

from django.conf.urls import include, url
from rest_framework.urlpatterns import format_suffix_patterns
from rest_framework_extensions.routers import ExtendedSimpleRouter as SimpleRouter

from ecommerce.core.constants import COURSE_ID_PATTERN, UUID_REGEX_PATTERN
from ecommerce.extensions.api.v2.views import assignmentemail as assignment_email
from ecommerce.extensions.api.v2.views import baskets as basket_views
from ecommerce.extensions.api.v2.views import catalog as catalog_views
from ecommerce.extensions.api.v2.views import checkout as checkout_views
from ecommerce.extensions.api.v2.views import coupons as coupon_views
from ecommerce.extensions.api.v2.views import courses as course_views
from ecommerce.extensions.api.v2.views import enterprise as enterprise_views
from ecommerce.extensions.api.v2.views import orders as order_views
from ecommerce.extensions.api.v2.views import partners as partner_views
from ecommerce.extensions.api.v2.views import payments as payment_views
from ecommerce.extensions.api.v2.views import products as product_views
from ecommerce.extensions.api.v2.views import providers as provider_views
from ecommerce.extensions.api.v2.views import publication as publication_views
from ecommerce.extensions.api.v2.views import refunds as refund_views
from ecommerce.extensions.api.v2.views import retirement as retirement_views
from ecommerce.extensions.api.v2.views import stockrecords as stockrecords_views
from ecommerce.extensions.api.v2.views import user_management as user_management_views
from ecommerce.extensions.api.v2.views import vouchers as voucher_views
from ecommerce.extensions.api.v2.views import webhooks as webhooks_views
from ecommerce.extensions.voucher.views import CouponReportCSVView

ORDER_NUMBER_PATTERN = r'(?P<number>[-\w]+)'
BASKET_ID_PATTERN = r'(?P<basket_id>[\d]+)'

# From edx-platform's lms/envs/common.py as of 2018-10-09
USERNAME_REGEX_PARTIAL = r'[\w .@_+-]+'
USERNAME_PATTERN = r'(?P<username>{regex})'.format(regex=USERNAME_REGEX_PARTIAL)

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
    url(r'^calculate/$', basket_views.BasketCalculateView.as_view(), name='calculate'),
]

PAYMENT_URLS = [
    url(r'^processors/$', payment_views.PaymentProcessorListView.as_view(), name='list_processors'),
]

WEBHOOKS_URLS = [
    url(r'^stripe/$', webhooks_views.StripeWebhooksView.as_view(), name='webhook_events'),
]

REFUND_URLS = [
    url(r'^$', refund_views.RefundCreateView.as_view(), name='create'),
    url(r'^(?P<pk>[\d]+)/process/$', refund_views.RefundProcessView.as_view(), name='process'),
]

RETIREMENT_URLS = [
    url(r'^tracking_id/{}/$'.format(USERNAME_PATTERN), retirement_views.EcommerceIdView.as_view(), name='tracking_id')
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

PROVIDER_URLS = [
    url(r'^$', provider_views.ProviderViewSet.as_view(), name='list_providers')
]

ENTERPRISE_URLS = [
    url(r'^customers$', enterprise_views.EnterpriseCustomerViewSet.as_view(), name='enterprise_customers'),
    url(
        r'^customer_catalogs$',
        enterprise_views.EnterpriseCustomerCatalogsViewSet.as_view({'get': 'get'}),
        name='enterprise_customer_catalogs'
    ),
    url(
        r'^customer_catalogs/(?P<enterprise_catalog_uuid>[^/]+)$',
        enterprise_views.EnterpriseCustomerCatalogsViewSet.as_view({'get': 'retrieve'}),
        name='enterprise_customer_catalog_details'
    ),
]

ASSIGNMENT_EMAIL_URLS = [
    url(r'^status/$', assignment_email.AssignmentEmailStatus.as_view(), name='update_status'),
]

USER_MANAGEMENT_URLS = [
    url(r'^replace_usernames/$', user_management_views.UsernameReplacementView.as_view(), name='username_replacement'),
]

urlpatterns = [
    url(r'^baskets/', include((BASKET_URLS, 'baskets'))),
    url(r'^checkout/', include((CHECKOUT_URLS, 'checkout'))),
    url(r'^coupons/', include((COUPON_URLS, 'coupons'))),
    url(r'^enterprise/', include((ENTERPRISE_URLS, 'enterprise'))),
    url(r'^payment/', include((PAYMENT_URLS, 'payment'))),
    url(r'^providers/', include((PROVIDER_URLS, 'providers'))),
    url(r'^publication/', include((ATOMIC_PUBLICATION_URLS, 'publication'))),
    url(r'^refunds/', include((REFUND_URLS, 'refunds'))),
    url(r'^retirement/', include((RETIREMENT_URLS, 'retirement'))),
    url(r'^user_management/', include((USER_MANAGEMENT_URLS, 'user_management'))),
    url(r'^assignment-email/', include((ASSIGNMENT_EMAIL_URLS, 'assignment-email'))),
    url(r'^webhooks/', include((WEBHOOKS_URLS, 'webhooks'))),
]

router = SimpleRouter()
router.register(r'basket-details', basket_views.BasketViewSet, basename='basket')
router.register(r'catalogs', catalog_views.CatalogViewSet, basename='catalog') \
    .register(r'products', product_views.ProductViewSet, basename='catalog-product',
              parents_query_lookups=['stockrecords__catalogs'])
router.register(r'coupons', coupon_views.CouponViewSet, basename='coupons')
router.register(r'enterprise/coupons', enterprise_views.EnterpriseCouponViewSet, basename='enterprise-coupons')
router.register(
    r'enterprise/offer_assignment_summary',
    enterprise_views.OfferAssignmentSummaryViewSet,
    basename='enterprise-offer-assignment-summary',
)
router.register(
    r'enterprise/offer-assignment-email-template/(?P<enterprise_customer>{})'.format(UUID_REGEX_PATTERN),
    enterprise_views.OfferAssignmentEmailTemplatesViewSet,
    basename='enterprise-offer-assignment-email-template',
)
router.register(
    r'enterprise/(?P<enterprise_customer>{})/enterprise-admin-offers'.format(UUID_REGEX_PATTERN),
    enterprise_views.EnterpriseAdminOfferApiViewSet,
    basename='enterprise-admin-offers-api',
)
router.register(
    r'enterprise/(?P<enterprise_customer>{})/enterprise-learner-offers'.format(UUID_REGEX_PATTERN),
    enterprise_views.EnterpriseLearnerOfferApiViewSet,
    basename='enterprise-learner-offers-api',
)
router.register(r'courses', course_views.CourseViewSet, basename='course') \
    .register(r'products', product_views.ProductViewSet,
              basename='course-product', parents_query_lookups=['course_id'])
router.register(r'orders', order_views.OrderViewSet, basename='order')
router.register(
    r'manual_course_enrollment_order',
    order_views.ManualCourseEnrollmentOrderViewSet,
    basename='manual-course-enrollment-order'
)
router.register(r'partners', partner_views.PartnerViewSet) \
    .register(r'catalogs', catalog_views.CatalogViewSet,
              basename='partner-catalogs', parents_query_lookups=['partner_id'])
router.register(r'partners', partner_views.PartnerViewSet) \
    .register(r'products', product_views.ProductViewSet,
              basename='partner-product', parents_query_lookups=['stockrecords__partner_id'])
router.register(r'products', product_views.ProductViewSet, basename='product')
router.register(r'vouchers', voucher_views.VoucherViewSet, basename='vouchers')
router.register(r'stockrecords', stockrecords_views.StockRecordViewSet, basename='stockrecords')

urlpatterns += router.urls
urlpatterns = format_suffix_patterns(urlpatterns)
