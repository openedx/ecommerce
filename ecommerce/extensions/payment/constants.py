"""Payment processor constants."""


from django.utils.translation import ugettext_lazy as _

CARD_TYPES = {
    'american_express': {
        'display_name': _('American Express'),
        'cybersource_code': '003',
        'apple_pay_network': 'amex',
        'stripe_brand': 'amex',
    },
    'diners': {
        'display_name': _('Diners'),
        'stripe_brand': 'diners',
    },
    'discover': {
        'display_name': _('Discover'),
        'cybersource_code': '004',
        'apple_pay_network': 'discover',
        'stripe_brand': 'discover',
    },
    'jcb': {
        'display_name': _('JCB'),
        'stripe_brand': 'jcb',
    },
    'mastercard': {
        'display_name': _('MasterCard'),
        'cybersource_code': '002',
        'apple_pay_network': 'mastercard',
        'stripe_brand': 'mastercard',
    },
    'unionpay': {
        'display_name': _('UnionPay'),
        'stripe_brand': 'unionpay',
    },
    'unknown': {
        'display_name': _('Unknown'),
        'stripe_brand': 'unknown',
    },
    'visa': {
        'display_name': _('Visa'),
        'cybersource_code': '001',
        'apple_pay_network': 'visa',
        'stripe_brand': 'visa',
    },
}

CARD_TYPE_CHOICES = ((key, value['display_name']) for key, value in CARD_TYPES.items())

# In Python 3.5 dicts aren't ordered so having this unsorted causes new migrations to happen on almost every
# run of makemigrations. Sorting fixes that. This can be removed in Python 3.6+.
CARD_TYPE_CHOICES = sorted(CARD_TYPE_CHOICES, key=lambda tup: tup[0])

CYBERSOURCE_CARD_TYPE_MAP = {
    value['cybersource_code']: key for key, value in CARD_TYPES.items() if 'cybersource_code' in value
}

CLIENT_SIDE_CHECKOUT_FLAG_NAME = 'enable_client_side_checkout'

# .. toggle_name: disable_microfrontend_for_basket_page
# .. toggle_type: waffle_flag
# .. toggle_default: False
# .. toggle_description: Allows viewing the old basket page even when using a new micro-frontend based basket page
# .. toggle_category: micro-frontend
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2019-10-03
# .. toggle_expiration_date: 2020-12-31
# .. toggle_tickets: DEPR-42
# .. toggle_status: supported
DISABLE_MICROFRONTEND_FOR_BASKET_PAGE_FLAG_NAME = 'disable_microfrontend_for_basket_page'

# Paypal only supports 4 languages, which are prioritized by country.
# https://developer.paypal.com/docs/classic/api/locale_codes/
PAYPAL_LOCALES = {
    'zh': 'CN',
    'fr': 'FR',
    'en': 'US',
    'es': 'MX',
}

APPLE_PAY_CYBERSOURCE_CARD_TYPE_MAP = {
    value['apple_pay_network']: value['cybersource_code'] for value in CARD_TYPES.values() if
    'cybersource_code' in value
}

STRIPE_CARD_TYPE_MAP = {
    value['stripe_brand']: key for key, value in CARD_TYPES.items() if 'stripe_brand' in value
}
