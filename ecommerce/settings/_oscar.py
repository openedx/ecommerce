"""Oscar-specific settings"""
from __future__ import absolute_import

from os.path import abspath, join, dirname

from django.core.urlresolvers import reverse_lazy
from oscar.defaults import *
from oscar import get_core_apps

from ecommerce.extensions.fulfillment.status import ORDER, LINE


# URL CONFIGURATION
OSCAR_HOMEPAGE = reverse_lazy('dashboard:index')
# END URL CONFIGURATION


# APP CONFIGURATION
OSCAR_APPS = [
    'ecommerce.extensions.api',
] + get_core_apps([
    'ecommerce.extensions.analytics',
    'ecommerce.extensions.catalogue',
    'ecommerce.extensions.order',
    'ecommerce.extensions.partner',
])
# END APP CONFIGURATION


# ORDER PROCESSING
# Prefix appended to every newly created order number.
ORDER_NUMBER_PREFIX = 'OSCR'

# The initial status for an order, or an order line.
OSCAR_INITIAL_ORDER_STATUS = ORDER.OPEN
OSCAR_INITIAL_LINE_STATUS = LINE.OPEN

# This dict defines the new order statuses than an order can move to
OSCAR_ORDER_STATUS_PIPELINE = {
    ORDER.OPEN: (ORDER.BEING_PROCESSED, ORDER.ORDER_CANCELLED,),
    ORDER.ORDER_CANCELLED: (),
    ORDER.BEING_PROCESSED: (ORDER.PAID, ORDER.PAYMENT_CANCELLED, ORDER.PAYMENT_ERROR),
    ORDER.PAYMENT_ERROR: (ORDER.PAID, ORDER.PAYMENT_CANCELLED),
    ORDER.PAYMENT_CANCELLED: (),
    ORDER.PAID: (ORDER.COMPLETE, ORDER.FULFILLMENT_ERROR,),
    ORDER.FULFILLMENT_ERROR: (ORDER.COMPLETE, ORDER.REFUNDED,),
    ORDER.COMPLETE: (ORDER.REFUNDED,),
    ORDER.REFUNDED: (),
}

# This is a dict defining all the statuses a single line in an order may have.
OSCAR_LINE_STATUS_PIPELINE = {
    LINE.OPEN: (LINE.BEING_PROCESSED, LINE.ORDER_CANCELLED,),
    LINE.ORDER_CANCELLED: (),
    LINE.BEING_PROCESSED: (LINE.PAID, LINE.PAYMENT_CANCELLED,),
    LINE.PAYMENT_CANCELLED: (),
    LINE.PAID: (
        LINE.COMPLETE,
        LINE.FULFILLMENT_CONFIGURATION_ERROR,
        LINE.FULFILLMENT_NETWORK_ERROR,
        LINE.FULFILLMENT_TIMEOUT_ERROR,
        LINE.FULFILLMENT_SERVER_ERROR,
    ),
    LINE.FULFILLMENT_CONFIGURATION_ERROR: (LINE.COMPLETE, LINE.REFUNDED,),
    LINE.FULFILLMENT_NETWORK_ERROR: (LINE.COMPLETE, LINE.REFUNDED,),
    LINE.FULFILLMENT_TIMEOUT_ERROR: (LINE.COMPLETE, LINE.REFUNDED,),
    LINE.FULFILLMENT_SERVER_ERROR: (LINE.COMPLETE, LINE.REFUNDED,),
    LINE.COMPLETE: (LINE.REFUNDED,),
    LINE.REFUNDED: (
        LINE.REVOKE_CONFIGURATION_ERROR,
        LINE.REVOKE_NETWORK_ERROR,
        LINE.REVOKE_TIMEOUT_ERROR,
        LINE.REVOKE_SERVER_ERROR,
    ),
    LINE.REVOKE_CONFIGURATION_ERROR: (),
    LINE.REVOKE_NETWORK_ERROR: (),
    LINE.REVOKE_TIMEOUT_ERROR: (),
    LINE.REVOKE_SERVER_ERROR: (),
}

# This dict defines the line statuses that will be set when an order's status
# is changed
OSCAR_ORDER_STATUS_CASCADE = {
    ORDER.OPEN: LINE.OPEN,
    ORDER.BEING_PROCESSED: LINE.BEING_PROCESSED,
    ORDER.ORDER_CANCELLED: LINE.ORDER_CANCELLED,
    ORDER.PAID: LINE.PAID,
    ORDER.PAYMENT_CANCELLED: LINE.PAYMENT_CANCELLED,
}

# Fulfillment Modules allows specific fulfillment modules to be evaluated in a specific order.
# Each fulfillment module supports handling a certain set of Product Types, and will evaluate the
# lines in the order to determine which it can fulfill.
FULFILLMENT_MODULES = [
    'ecommerce.extensions.fulfillment.modules.EnrollmentFulfillmentModule',
]

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    },
}

AUTHENTICATION_BACKENDS = (
    'oscar.apps.customer.auth_backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
)

OSCAR_DEFAULT_CURRENCY = 'USD'
# END ORDER PROCESSING


# RATE LIMITING
ORDERS_ENDPOINT_RATE_LIMIT = '40/minute'
# END RATE LIMITING


# PAYMENT PROCESSING
PAYMENT_PROCESSORS = (
    'ecommerce.extensions.payment.processors.Cybersource',
)

PAYMENT_PROCESSOR_CONFIG = {
    'cybersource': {
        'profile_id': 'set-me-please',
        'access_key': 'set-me-please',
        'secret_key': 'set-me-please',
        'pay_endpoint': 'https://replace-me/',
    }
}
# END PAYMENT PROCESSING


# ANALYTICS
# Here Be Dragons: Use this feature flag to control whether Oscar should install its
# default analytics receivers. This is disabled by default. Some default receivers,
# such as the receiver responsible for tallying product orders, make row-locking
# queries which significantly degrade performance at scale.
INSTALL_DEFAULT_ANALYTICS_RECEIVERS = False
# END ANALYTICS
