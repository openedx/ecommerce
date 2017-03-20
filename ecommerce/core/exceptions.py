class MissingRequestError(Exception):
    """ Raised when the current request is missing from threadlocal storage """
    pass


class SiteConfigurationError(Exception):
    """ Raised when SiteConfiguration is invalid. """
    pass
