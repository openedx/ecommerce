import logging
import re
from urllib.parse import urljoin

from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.extensions.analytics.utils import parse_tracking_context

logger = logging.getLogger(__name__)
Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
User = get_user_model()


def get_basket_program_uuid(basket):
    """
    Return the program UUID associated with the given basket, if one exists.
    Arguments:
        basket (Basket): The basket object.
    Returns:
        string: The program UUID if the basket is associated with a bundled purchase, otherwise None.
    """
    try:
        attribute_type = BasketAttributeType.objects.get(name='bundle_identifier')
    except BasketAttributeType.DoesNotExist:
        return None
    bundle_attributes = BasketAttribute.objects.filter(
        basket=basket,
        attribute_type=attribute_type
    )
    bundle_attribute = bundle_attributes.first()
    return bundle_attribute.value_text if bundle_attribute else None


def get_program_uuid(order):
    """
    Return the program UUID associated with the given order, if one exists.

    Arguments:
        order (Order): The order object.

    Returns:
        string: The program UUID if the order is associated with a bundled purchase, otherwise None.
    """
    return get_basket_program_uuid(order.basket)


def middle_truncate(provided_string, chars):
    """Truncate the provided string, if necessary.

    Cuts excess characters from the middle of the string and replaces
    them with a string indicating that truncation has occurred.

    Arguments:
        provided_string (unicode or str): The string to be truncated.
        chars (int): The character limit for the truncated string.

    Returns:
        Unicode: The truncated string, of length less than or equal to `chars`.
            If no truncation was required, the original string is returned.

    Raises:
        ValueError: If the provided character limit is less than the length of
            the truncation indicator.
    """
    if len(provided_string) <= chars:
        return provided_string

    # Translators: This is a string placed in the middle of a truncated string
    # to indicate that truncation has occurred. For example, if a title may only
    # be at most 11 characters long, "A Very Long Title" (17 characters) would be
    # truncated to "A Ve...itle".
    indicator = _('...')

    indicator_length = len(indicator)
    if chars < indicator_length:
        raise ValueError

    slice_size = (chars - indicator_length) // 2
    start, end = provided_string[:slice_size], provided_string[-slice_size:]
    truncated = u'{start}{indicator}{end}'.format(start=start, indicator=indicator, end=end)

    return truncated


def clean_field_value(value):
    """Strip the value of any special characters.

    Currently strips caret(^), colon(:) and quote(" ') characters from the value.

    Args:
        value (str): The original value.

    Returns:
        A cleaned string.
    """
    return re.sub(r'[\^:"\']', '', value)


def embargo_check(user, site, products, ip=None):
    """ Checks if the user has access to purchase products by calling the LMS embargo API.

    Args:
        request : The current request
        products (list): A list of products to check access against

    Returns:
        Bool
    """

    courses = []

    if not ip and isinstance(user, User):
        _, _, ip = parse_tracking_context(user, usage='embargo')

    for product in products:
        # We only are checking Seats
        if product.get_product_class().name == SEAT_PRODUCT_CLASS_NAME:
            courses.append(product.course.id)

    if courses:
        params = {
            'user': user,
            'ip_address': ip,
            'course_ids': courses
        }

        try:
            api_client = site.siteconfiguration.oauth_api_client
            api_url = urljoin(f"{site.siteconfiguration.embargo_api_url}/", "course_access/")
            response = api_client.get(api_url, params=params).json()
            return response.get('access', True)
        except:  # pylint: disable=bare-except
            # We are going to allow purchase if the API is un-reachable.
            pass

    return True
