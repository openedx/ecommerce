class MissingRequestError(Exception):
    """ Raised when the current request is missing from threadlocal storage """


class SiteConfigurationError(Exception):
    """ Raised when SiteConfiguration is invalid. """


class MissingLmsUserIdException(Exception):
    """Exception indicating the user is missing an LMS user id. """
