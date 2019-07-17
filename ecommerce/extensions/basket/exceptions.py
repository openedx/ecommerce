"""Exceptions used by Basket."""


class BadRequestException(Exception):
    pass


class RedirectException(Exception):
    def __init__(self, message=None, response=None):
        super(RedirectException, self).__init__(message)
        self.response = response


class VoucherException(Exception):
    pass
