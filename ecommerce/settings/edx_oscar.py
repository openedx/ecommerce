""" Oscar Specific Settings """
from __future__ import absolute_import

# Order processing
# ================

# The initial status for an order, or an order line.
OSCAR_INITIAL_ORDER_STATUS = 'Open'
OSCAR_INITIAL_LINE_STATUS = 'Open'

# This dict defines the new order statuses than an order can move to
OSCAR_ORDER_STATUS_PIPELINE = {
    'Open': ('Being Processed', 'Order Cancelled',),
    'Order Cancelled': (),
    'Being Processed': ('Paid', 'Payment Cancelled',),
    'Payment Cancelled': (),
    'Paid': ('Complete', 'Fulfillment Error',),
    'Fulfillment Error': ('Complete', 'Refunded',),
    'Complete': ('Refunded',),
    'Refunded': (),
}

# This dict defines the line statuses that will be set when an order's status
# is changed
OSCAR_ORDER_STATUS_CASCADE = {
    'Being Processed': 'Being Processed',
    'Paid': 'Paid',
    'Cancelled': 'Cancelled',
    'Complete': 'Fulfilled',
    'Refunded': 'Refunded',
}

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.simple_backend.SimpleEngine',
    },
}

# TODO: Replace with new Authentication backend
AUTHENTICATION_BACKENDS = (
    'oscar.apps.customer.auth_backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
)

OSCAR_DEFAULT_CURRENCY = 'USD'