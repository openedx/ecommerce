"""
Exceptions used by the Order app.
"""


class AlreadyPlacedOrderException(Exception):
    """
    Exception for user if he has already placed an order for course
    """
