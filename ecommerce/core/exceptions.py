class MissingRequestError(Exception):
    """ Raised when the current request is missing from threadlocal storage """
    pass
