"""Oscar-specific settings"""


from django.utils.translation import ugettext_lazy as _
from oscar.defaults import *

from ecommerce.extensions.fulfillment.status import LINE, ORDER
from ecommerce.extensions.refund.status import REFUND, REFUND_LINE

# URL CONFIGURATION
OSCAR_HOMEPAGE = reverse_lazy('dashboard:index')
# END URL CONFIGURATION


# APP CONFIGURATION
OSCAR_APPS = [
    'oscar',
    'oscar.apps.address',
    'oscar.apps.shipping',
    'oscar.apps.catalogue.reviews',
    'oscar.apps.search',
    'oscar.apps.wishlists',

    'ecommerce.extensions',
    'ecommerce.extensions.iap',
    'ecommerce.extensions.api',
    'ecommerce.extensions.communication.apps.CommunicationConfig',
    'ecommerce.extensions.fulfillment',
    'ecommerce.extensions.refund',
    'ecommerce.extensions.analytics',
    'ecommerce.extensions.basket',
    'ecommerce.extensions.catalogue',
    'ecommerce.extensions.checkout',
    'ecommerce.extensions.customer',
    'ecommerce.extensions.offer',
    'ecommerce.extensions.order',
    'ecommerce.extensions.partner',
    'ecommerce.extensions.payment',
    'ecommerce.extensions.voucher',

    # Dashboard applications depend on models declared in the core applications (basket, catalogue, etc).
    # To prevent issues with Oscar’s dynamic model loading, overrides of dashboard applications should
    # follow overrides of core applications
    'oscar.apps.dashboard.reports',
    'oscar.apps.dashboard.partners',
    'oscar.apps.dashboard.pages',
    'oscar.apps.dashboard.ranges',
    'oscar.apps.dashboard.reviews',
    'oscar.apps.dashboard.vouchers',
    'oscar.apps.dashboard.communications',
    'oscar.apps.dashboard.shipping',

    'ecommerce.extensions.dashboard',
    'ecommerce.extensions.dashboard.catalogue',
    'ecommerce.extensions.dashboard.offers',
    'ecommerce.extensions.dashboard.refunds',
    'ecommerce.extensions.dashboard.orders',
    'ecommerce.extensions.dashboard.users',

    # 3rd-party apps that oscar depends on
    'haystack',
    'treebeard',
    'django_tables2',
    'sorl.thumbnail',
]
# END APP CONFIGURATION


# ORDER PROCESSING

# The initial status for an order, or an order line.
OSCAR_INITIAL_ORDER_STATUS = ORDER.OPEN
OSCAR_INITIAL_LINE_STATUS = LINE.OPEN

# This dict defines the new order statuses than an order can move to
OSCAR_ORDER_STATUS_PIPELINE = {
    ORDER.PENDING: (ORDER.OPEN, ORDER.PAYMENT_ERROR),
    ORDER.PAYMENT_ERROR: (),
    ORDER.OPEN: (ORDER.COMPLETE, ORDER.FULFILLMENT_ERROR),
    ORDER.FULFILLMENT_ERROR: (ORDER.COMPLETE,),
    ORDER.COMPLETE: ()
}

# This is a dict defining all the statuses a single line in an order may have.
OSCAR_LINE_STATUS_PIPELINE = {
    LINE.OPEN: (
        LINE.COMPLETE,
        LINE.FULFILLMENT_CONFIGURATION_ERROR,
        LINE.FULFILLMENT_NETWORK_ERROR,
        LINE.FULFILLMENT_TIMEOUT_ERROR,
        LINE.FULFILLMENT_SERVER_ERROR,
    ),
    LINE.FULFILLMENT_CONFIGURATION_ERROR: (LINE.COMPLETE,),
    LINE.FULFILLMENT_NETWORK_ERROR: (LINE.COMPLETE,),
    LINE.FULFILLMENT_TIMEOUT_ERROR: (LINE.COMPLETE,),
    LINE.FULFILLMENT_SERVER_ERROR: (LINE.COMPLETE,),
    LINE.COMPLETE: (),
}

# This dict defines the line statuses that will be set when an order's status is changed
OSCAR_ORDER_STATUS_CASCADE = {
    ORDER.OPEN: LINE.OPEN,
}

# Fulfillment Modules allows specific fulfillment modules to be evaluated in a specific order.
# Each fulfillment module supports handling a certain set of Product Types, and will evaluate the
# lines in the order to determine which it can fulfill.
FULFILLMENT_MODULES = [
    'ecommerce.extensions.fulfillment.modules.EnrollmentFulfillmentModule',
    'ecommerce.extensions.fulfillment.modules.CouponFulfillmentModule',
    'ecommerce.extensions.fulfillment.modules.EnrollmentCodeFulfillmentModule',
    'ecommerce.extensions.fulfillment.modules.CourseEntitlementFulfillmentModule',
    'ecommerce.extensions.fulfillment.modules.DonationsFromCheckoutTestFulfillmentModule',
    'ecommerce.extensions.fulfillment.modules.ExecutiveEducation2UFulfillmentModule'
]

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    },
}

AUTHENTICATION_BACKENDS = (
    'rules.permissions.ObjectPermissionBackend',
    'oscar.apps.customer.auth_backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
)

OSCAR_DEFAULT_CURRENCY = 'USD'
# END ORDER PROCESSING


# PAYMENT PROCESSING
PAYMENT_PROCESSORS = (
    'ecommerce.extensions.iap.processors.android_iap.AndroidIAP',
    'ecommerce.extensions.iap.processors.ios_iap.IOSIAP',
    'ecommerce.extensions.payment.processors.cybersource.Cybersource',
    'ecommerce.extensions.payment.processors.cybersource.CybersourceREST',
    'ecommerce.extensions.payment.processors.paypal.Paypal',
    'ecommerce.extensions.payment.processors.stripe.Stripe',
)

PAYMENT_PROCESSOR_RECEIPT_PATH = '/checkout/receipt/'
PAYMENT_PROCESSOR_CANCEL_PATH = '/checkout/cancel-checkout/'
PAYMENT_PROCESSOR_ERROR_PATH = '/checkout/error/'

PAYMENT_PROCESSOR_CONFIG = {
    'edx': {
        'cybersource': {
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'send_level_2_3_details': True,
            'apple_pay_merchant_identifier': '',
            'apple_pay_merchant_id_domain_association': '',
            'apple_pay_merchant_id_certificate_path': '',
            'apple_pay_country_code': '',
        },
        'cybersource-rest': {
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'send_level_2_3_details': True,
            'apple_pay_merchant_identifier': '',
            'apple_pay_merchant_id_domain_association': '',
            'apple_pay_merchant_id_certificate_path': '',
            'apple_pay_country_code': '',
        },
        'paypal': {
            # 'mode' can be either 'sandbox' or 'live'
            'mode': None,
            'client_id': None,
            'client_secret': None,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
        },
        'stripe': {
            'api_version': '2022-08-01; server_side_confirmation_beta=v1',
            'enable_telemetry': None,
            'log_level': None,
            'max_network_retries': 0,
            'proxy': None,
            'publishable_key': None,
            'secret_key': None,
            'webhook_endpoint_secret': None,
            'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'receipt_url': PAYMENT_PROCESSOR_RECEIPT_PATH,
        },
        'android-iap': {
            'google_bundle_id': '<put-value-here>',
            'google_service_account_key_file': '<put-value-here>'
        },
        'ios-iap': {
            'ios_bundle_id': '<put-value-here>',
        }
    },
}

PAYMENT_PROCESSOR_SWITCH_PREFIX = 'payment_processor_active_'
# END PAYMENT PROCESSING


# ANALYTICS
# Here Be Dragons: Use this feature flag to control whether Oscar should install its
# default analytics receivers. This is disabled by default. Some default receivers,
# such as the receiver responsible for tallying product orders, make row-locking
# queries which significantly degrade performance at scale.
INSTALL_DEFAULT_ANALYTICS_RECEIVERS = False
# END ANALYTICS


# REFUND PROCESSING
OSCAR_INITIAL_REFUND_STATUS = REFUND.OPEN
OSCAR_INITIAL_REFUND_LINE_STATUS = REFUND_LINE.OPEN

OSCAR_REFUND_STATUS_PIPELINE = {
    REFUND.OPEN: (REFUND.DENIED, REFUND.PAYMENT_REFUND_ERROR, REFUND.PAYMENT_REFUNDED),
    REFUND.PAYMENT_REFUND_ERROR: (REFUND.PAYMENT_REFUNDED, REFUND.PAYMENT_REFUND_ERROR),
    REFUND.PAYMENT_REFUNDED: (REFUND.REVOCATION_ERROR, REFUND.COMPLETE),
    REFUND.REVOCATION_ERROR: (REFUND.REVOCATION_ERROR, REFUND.COMPLETE),
    REFUND.DENIED: (),
    REFUND.COMPLETE: ()
}

OSCAR_REFUND_LINE_STATUS_PIPELINE = {
    REFUND_LINE.OPEN: (REFUND_LINE.DENIED, REFUND_LINE.REVOCATION_ERROR, REFUND_LINE.COMPLETE),
    REFUND_LINE.REVOCATION_ERROR: (REFUND_LINE.REVOCATION_ERROR, REFUND_LINE.COMPLETE),
    REFUND_LINE.DENIED: (),
    REFUND_LINE.COMPLETE: ()
}
# END REFUND PROCESSING

# DASHBOARD NAVIGATION MENU
OSCAR_DASHBOARD_NAVIGATION = [
    {
        'label': _('Dashboard'),
        'icon': 'icon-th-list',
        'url_name': 'dashboard:index',
    },
    {
        'label': _('Catalogue'),
        'icon': 'icon-sitemap',
        'children': [
            {
                'label': _('Products'),
                'url_name': 'dashboard:catalogue-product-list',
            },
            {
                'label': _('Product Types'),
                'url_name': 'dashboard:catalogue-class-list',
            },
            {
                'label': _('Categories'),
                'url_name': 'dashboard:catalogue-category-list',
            },
            {
                'label': _('Ranges'),
                'url_name': 'dashboard:range-list',
            },
            {
                'label': _('Low stock alerts'),
                'url_name': 'dashboard:stock-alert-list',
            },
        ]
    },
    {
        'label': _('Fulfillment'),
        'icon': 'icon-shopping-cart',
        'children': [
            {
                'label': _('Orders'),
                'url_name': 'dashboard:order-list',
            },
            {
                'label': _('Statistics'),
                'url_name': 'dashboard:order-stats',
            },
            {
                'label': _('Partners'),
                'url_name': 'dashboard:partner-list',
            },
            {
                'label': _('Refunds'),
                'url_name': 'dashboard:refunds-list',
            },
        ]
    },
    {
        'label': _('Customers'),
        'icon': 'icon-group',
        'children': [
            {
                'label': _('Customers'),
                'url_name': 'dashboard:users-index',
            },
            {
                'label': _('Stock alert requests'),
                'url_name': 'dashboard:user-alert-list',
            },
        ]
    },
    {
        'label': _('Offers'),
        'icon': 'icon-bullhorn',
        'children': [
            {
                'label': _('Offers'),
                'url_name': 'dashboard:offer-list',
            },
            {
                'label': _('Vouchers'),
                'url_name': 'dashboard:voucher-list',
            },
        ],
    },
    {
        'label': _('Reports'),
        'icon': 'icon-bar-chart',
        'url_name': 'dashboard:reports-index',
    },
]
# END DASHBOARD NAVIGATION MENU

# Default timeout for Enrollment API calls
ENROLLMENT_FULFILLMENT_TIMEOUT = 7

# Coupon code length
VOUCHER_CODE_LENGTH = 16

THUMBNAIL_DEBUG = False

OSCAR_FROM_EMAIL = 'testing@example.com'
