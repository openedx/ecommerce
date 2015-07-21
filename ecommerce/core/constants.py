"""Health check constants."""

ISO_8601_FORMAT = u'%Y-%m-%dT%H:%M:%SZ'


class Status(object):
    """Health statuses."""
    OK = u"OK"
    UNAVAILABLE = u"UNAVAILABLE"


class UnavailabilityMessage(object):
    """Messages to be logged when services are unavailable."""
    DATABASE = u"Unable to connect to database"
    LMS = u"Unable to connect to LMS"
