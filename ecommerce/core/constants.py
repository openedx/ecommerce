"""Constants core to the ecommerce app."""

ISO_8601_FORMAT = u'%Y-%m-%dT%H:%M:%SZ'


# Regex used to match course IDs.
COURSE_ID_REGEX = r'[^/+]+(/|\+)[^/+]+(/|\+)[^/]+'
COURSE_ID_PATTERN = r'(?P<course_id>{})'.format(COURSE_ID_REGEX)


# Seat constants
SEAT_PRODUCT_CLASS_NAME = "Seat"


# Enrollment Code constants
ENROLLMENT_CODE_PRODUCT_CLASS_NAME = 'Enrollment Code'
ENROLLMENT_CODE_SWITCH = 'create_enrollment_codes'
ENROLLMENT_CODE_SEAT_TYPES = ['verified', 'professional', 'no-id-professional']

# Course Catalog constants
DEFAULT_CATALOG_PAGE_SIZE = 10000


class Status(object):
    """Health statuses."""
    OK = u"OK"
    UNAVAILABLE = u"UNAVAILABLE"


class UnavailabilityMessage(object):
    """Messages to be logged when services are unavailable."""
    DATABASE = u"Unable to connect to database"
    LMS = u"Unable to connect to LMS"
