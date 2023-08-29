"""
Exceptions used by the iap v1 api.
"""


class RefundCompletionException(Exception):
    """
    Exception if a refund is not approved
    """
