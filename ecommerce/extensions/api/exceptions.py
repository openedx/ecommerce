"""Exceptions and error messages used by the ecommerce API."""


from django.utils.translation import ugettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException

PRODUCT_OBJECTS_MISSING_DEVELOPER_MESSAGE = u"No product objects could be found in the request body"
PRODUCT_OBJECTS_MISSING_USER_MESSAGE = _("You can't check out with an empty basket.")

SKU_NOT_FOUND_DEVELOPER_MESSAGE = u"SKU missing from a requested product object"
SKU_NOT_FOUND_USER_MESSAGE = _("We couldn't locate the identification code necessary to find one of your products.")

PRODUCT_NOT_FOUND_DEVELOPER_MESSAGE = u"Catalog does not contain a product with SKU [{sku}]"
PRODUCT_NOT_FOUND_USER_MESSAGE = _("We couldn't find one of the products you're looking for.")

PRODUCT_UNAVAILABLE_DEVELOPER_MESSAGE = u"Product with SKU [{sku}] is [{availability}]"
PRODUCT_UNAVAILABLE_USER_MESSAGE = _("One of the products you're trying to order is unavailable.")

LMS_USER_ID_NOT_FOUND_DEVELOPER_MESSAGE = u'Could not find lms_user_id for user [{user_id}]'
LMS_USER_ID_NOT_FOUND_USER_MESSAGE = _("We couldn't find enough information about you to perform the calculation.")


class ApiError(Exception):
    """Standard error raised by the API."""


class ProductNotFoundError(ApiError):
    """Raised when the provided SKU does not correspond to a product in the catalog."""


class BadRequestException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


# TODO: LEARNER-5197: Remove this exception when the atomic transaction code is deleted.
class TemporaryBasketException(Exception):
    """Exception raised to force a transaction rollback so that the temporary basket
    is not saved to the database."""
