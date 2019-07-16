"""Constants core to the ecommerce app."""
from __future__ import unicode_literals

ISO_8601_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

# Regex used to match course IDs.
COURSE_ID_REGEX = r'[^/+]+(/|\+)[^/+]+(/|\+)[^/]+'
COURSE_ID_PATTERN = r'(?P<course_id>{})'.format(COURSE_ID_REGEX)

# Seat constants
SEAT_PRODUCT_CLASS_NAME = 'Seat'

# switch is used to disable/enable USER table list/change view in django admin
USER_LIST_VIEW_SWITCH = 'enable_user_list_view'

# Coupon constant
COUPON_PRODUCT_CLASS_NAME = 'Coupon'

# Donations from checkout tests constant
# Don't use this code for your own purposes, thanks.
DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME = 'Donation'

# Enrollment Code constants
ENROLLMENT_CODE_PRODUCT_CLASS_NAME = 'Enrollment Code'
ENROLLMENT_CODE_SWITCH = 'create_enrollment_codes'
ENROLLMENT_CODE_SEAT_TYPES = ['verified', 'professional', 'no-id-professional']

# Course Entitlement constant
COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME = 'Course Entitlement'

# Discovery Service constants
DEFAULT_CATALOG_PAGE_SIZE = 100

ENTERPRISE_COUPON_ADMIN_ROLE = 'enterprise_coupon_admin'
ORDER_MANAGER_ROLE = 'order_manager'

SYSTEM_ENTERPRISE_ADMIN_ROLE = 'enterprise_admin'
SYSTEM_ENTERPRISE_LEARNER_ROLE = 'enterprise_learner'
SYSTEM_ENTERPRISE_OPERATOR_ROLE = 'enterprise_openedx_operator'

# Context to give access to all resources
ALL_ACCESS_CONTEXT = '*'


class Status(object):
    """Health statuses."""
    OK = 'OK'
    UNAVAILABLE = 'UNAVAILABLE'


class UnavailabilityMessage(object):
    """Messages to be logged when services are unavailable."""
    DATABASE = 'Unable to connect to database'
    LMS = 'Unable to connect to LMS'
