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

# Email Template Types
ASSIGN, REMIND, REVOKE = ('assign', 'remind', 'revoke')
EMAIL_TEMPLATE_TYPES = (
    (ASSIGN, _('Assign')),
    (REMIND, _('Remind')),
    (REVOKE, _('Revoke')),
)

# Don't change it, These is being used in data migration '0047_codeassignmentnudgeemailtemplates'
TEMPLATES_NAME = ['Day 3 Nudge Email', 'Day 10 Nudge Email', 'Day 19 Nudge Email']
NUDGE_EMAIL_TEMPLATES = [
    {
        'email_type': DAY3,
        'email_greeting': 'Remember when your organization gave you a code to learn on edX? We do, and we\'re glad to '
                          'have you! Come see what you can learn.',
        'email_closing': 'Redeem your edX code and start learning today.',
        'email_subject': 'Start learning on edX!',
        'name': TEMPLATES_NAME[0],
    },
    {
        'email_type': DAY10,
        'email_greeting': 'Many learners from your organization are completing more problems every week, and are '
                          'learning new skills. What do you want to start learning?',
        'email_closing': 'Join your peers, and start learning today.',
        'email_subject': 'Join the learning on edX!',
        'name': TEMPLATES_NAME[1],
    },
    {
        'email_type': DAY19,
        'email_greeting': 'Learners like you are earning certificates from some of the top universities and companies '
                          'in the world. Will you join them?',
        'email_closing': 'Learn from the best, and redeem your code today.',
        'email_subject': 'It\'s not to late redeem your edX code!',
        'name': TEMPLATES_NAME[2],
    },
]
