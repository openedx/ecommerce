class REFUND(object):
    OPEN = 'Open'
    DENIED = 'Denied'
    PENDING_WITH_REVOCATION = 'Pending With Revocation'
    PENDING_WITHOUT_REVOCATION = 'Pending Without Revocation'
    PAYMENT_REFUND_ERROR = 'Payment Refund Error'
    PAYMENT_REFUNDED = 'Payment Refunded'
    REVOCATION_ERROR = 'Revocation Error'
    COMPLETE = 'Complete'


class REFUND_LINE(object):
    OPEN = 'Open'
    PENDING_WITH_REVOCATION = 'Pending With Revocation'
    PENDING_WITHOUT_REVOCATION = 'Pending Without Revocation'
    REVOCATION_ERROR = 'Revocation Error'
    DENIED = 'Denied'
    COMPLETE = 'Complete'
