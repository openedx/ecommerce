"""Payment processor constants."""
from __future__ import absolute_import, unicode_literals

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

# .. toggle_name: enable_microfrontend_for_basket_page
# .. toggle_type: waffle_flag
# .. toggle_default: False
# .. toggle_description: Supports staged rollout of a new micro-frontend-based implementation of the basket page.
# .. toggle_category: micro-frontend
# .. toggle_use_cases: incremental_release, open_edx
# .. toggle_creation_date: 2019-06-25
# .. toggle_expiration_date: 2020-12-31
# .. toggle_warnings: Also set SiteConfiguration for enable_microfrontend_for_basket_page and payment_microfrontend_url.
# .. toggle_tickets: DEPR-42
# .. toggle_status: supported
ENABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME = 'enable_microfrontend_for_basket_page'

# .. toggle_name: force_microfrontend_for_basket_page
# .. toggle_type: waffle_flag
# .. toggle_default: False
# .. toggle_description: Supports manual testing of a new micro-frontend-based implementation of the basket page.
# .. toggle_category: micro-frontend
# .. toggle_use_cases: testing, open_edx
# .. toggle_creation_date: 2019-07-29
# .. toggle_expiration_date: 2019-12-31
# .. toggle_warnings: See enable_microfrontend_for_basket_page
# .. toggle_tickets: DEPR-42
# .. toggle_status: supported
FORCE_MICROFRONTEND_BUCKET_FLAG_NAME = 'force_microfrontend_bucket'

# Bucket id for users being bucketed into the Payment MFE
PAYMENT_MFE_BUCKET = 1

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
