"""Payment processor constants."""
from __future__ import unicode_literals

import six
from django.utils.translation import ugettext_lazy as _

CARD_TYPES = {
    'american_express': {
        'display_name': _('American Express'),
        'cybersource_code': '003',
        'apple_pay_network': 'amex',
        'stripe_brand': 'American Express',
    },
    'discover': {
        'display_name': _('Discover'),
        'cybersource_code': '004',
        'apple_pay_network': 'discover',
        'stripe_brand': 'Discover',
    },
    'mastercard': {
        'display_name': _('MasterCard'),
        'cybersource_code': '002',
        'apple_pay_network': 'mastercard',
        'stripe_brand': 'MasterCard',
    },
    'visa': {
        'display_name': _('Visa'),
        'cybersource_code': '001',
        'apple_pay_network': 'visa',
        'stripe_brand': 'Visa',
    },
}

CARD_TYPE_CHOICES = ((key, value['display_name']) for key, value in six.iteritems(CARD_TYPES))
CYBERSOURCE_CARD_TYPE_MAP = {
    value['cybersource_code']: key for key, value in six.iteritems(CARD_TYPES) if 'cybersource_code' in value
}

CLIENT_SIDE_CHECKOUT_FLAG_NAME = 'enable_client_side_checkout'

# Paypal only supports 4 languages, which are prioritized by country.
# https://developer.paypal.com/docs/classic/api/locale_codes/
PAYPAL_LOCALES = {
    'zh': 'CN',
    'fr': 'FR',
    'en': 'US',
    'es': 'MX',
}

APPLE_PAY_CYBERSOURCE_CARD_TYPE_MAP = {
    value['apple_pay_network']: value['cybersource_code'] for value in six.itervalues(CARD_TYPES) if
    'cybersource_code' in value
}

STRIPE_CARD_TYPE_MAP = {
    value['stripe_brand']: key for key, value in six.iteritems(CARD_TYPES) if 'stripe_brand' in value
}

VOUCHER_VALIDATION_BEFORE_PAYMENT = 'voucher_validation_before_payment'
