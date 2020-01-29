"""Exceptions used by Basket."""


class BadRequestException(Exception):
    """ Basket Bad Request Exception. """


class RedirectException(Exception):
    def __init__(self, message=None, response=None):
        super(RedirectException, self).__init__(message)
        self.response = response


class VoucherException(Exception):
    """ Voucher Exception. """
