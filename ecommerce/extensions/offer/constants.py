from django.utils.translation import ugettext_lazy as _

DYNAMIC_DISCOUNT_FLAG = 'offer.dynamic_discount'

# OfferAssignment status constants defined here to avoid circular dependency.
OFFER_ASSIGNMENT_EMAIL_PENDING = 'EMAIL_PENDING'
OFFER_ASSIGNED = 'ASSIGNED'
OFFER_REDEEMED = 'REDEEMED'
OFFER_ASSIGNMENT_EMAIL_BOUNCED = 'EMAIL_BOUNCED'
OFFER_ASSIGNMENT_REVOKED = 'REVOKED'

OFFER_MAX_USES_DEFAULT = 10000

# Coupon code filters
VOUCHER_NOT_ASSIGNED = 'unassigned'
VOUCHER_NOT_REDEEMED = 'unredeemed'
VOUCHER_PARTIAL_REDEEMED = 'partially-redeemed'
VOUCHER_REDEEMED = 'redeemed'

# Coupon visibility filters
VOUCHER_IS_PUBLIC = 'public'
VOUCHER_IS_PRIVATE = 'private'

OFFER_ASSIGNMENT_EMAIL_TEMPLATE_FIELD_LIMIT = 50000
OFFER_ASSIGNMENT_EMAIL_SUBJECT_LIMIT = 1000


# Code Assignment Nudge email templates.
DAY3, DAY10, DAY19 = ('Day3', 'Day10', 'Day19')
NUDGE_EMAIL_CYCLE = {'3': DAY3, '10': DAY10, '19': DAY19}
NUDGE_EMAIL_TEMPLATE_TYPES = (
    (DAY3, _('Day 3')),
    (DAY10, _('Day 10')),
    (DAY19, _('Day 19')),
)
