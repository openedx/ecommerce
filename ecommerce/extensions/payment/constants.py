"""Payment processor constants."""


class ProcessorConstants(object):
    """ Constants that are used by all payment processors """
    ORDER_NUMBER = 'order_number'
    SUCCESS = 'success'
    PAID_EVENT_NAME = 'Paid'


class CybersourceFieldNames(object):
    """CyberSource request field names."""
    ACCESS_KEY = u'access_key'
    PROFILE_ID = u'profile_id'
    REFERENCE_NUMBER = u'reference_number'
    REQ_REFERENCE_NUMBER = u'req_reference_number'
    TRANSACTION_UUID = u'transaction_uuid'
    TRANSACTION_TYPE = u'transaction_type'
    PAYMENT_METHOD = u'payment_method'
    CURRENCY = u'currency'
    REQ_CURRENCY = u'req_currency'
    AMOUNT = u'amount'
    LOCALE = u'locale'
    OVERRIDE_CUSTOM_RECEIPT_PAGE = u'override_custom_receipt_page'
    OVERRIDE_CUSTOM_CANCEL_PAGE = u'override_custom_cancel_page'
    MERCHANT_DEFINED_DATA_BASE = u'merchant_defined_data'
    SIGNED_DATE_TIME = u'signed_date_time'
    SIGNED_FIELD_NAMES = u'signed_field_names'
    UNSIGNED_FIELD_NAMES = u'unsigned_field_names'
    SIGNATURE = u'signature'
    AUTH_AMOUNT = u'auth_amount'
    DECISION = u'decision'


class CybersourceConstants(object):
    """Constants used by the CyberSource processor implementation."""
    NAME = u'cybersource'
    TRANSACTION_TYPE = u'sale'
    PAYMENT_METHOD = u'card'
    ISO_8601_FORMAT = u'%Y-%m-%dT%H:%M:%SZ'
    MAX_OPTIONAL_FIELDS = 100
    MESSAGE_SUBSTRUCTURE = u'{key}={value}'
    FIELD_NAMES = CybersourceFieldNames()
    UNSIGNED_FIELD_NAMES = u''
    SEPARATOR = u','
    CANCEL = u'CANCEL'
    DECLINE = u'DECLINE'
    ACCEPT = u'ACCEPT'
    ERROR = u'ERROR'
