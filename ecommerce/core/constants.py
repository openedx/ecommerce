"""Constants core to the ecommerce app."""

ISO_8601_FORMAT = u'%Y-%m-%dT%H:%M:%SZ'


# Regex used to match course IDs.
COURSE_ID_REGEX = r'[^/+]+(/|\+)[^/+]+(/|\+)[^/]+'
COURSE_ID_PATTERN = r'(?P<course_id>{})'.format(COURSE_ID_REGEX)

# Enrollment code product class name.
ENROLLMENT_CODE = 'Enrollment code'


class Status(object):
    """Health statuses."""
    OK = u"OK"
    UNAVAILABLE = u"UNAVAILABLE"


class UnavailabilityMessage(object):
    """Messages to be logged when services are unavailable."""
    DATABASE = u"Unable to connect to database"
    LMS = u"Unable to connect to LMS"
