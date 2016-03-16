"""Functions used for data retrieval and manipulation by the API."""
import logging
import requests

from django.conf import settings
from oscar.core.loading import get_model, get_class

from ecommerce.extensions.api import exceptions
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.settings import get_lms_url

NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
Product = get_model('catalogue', 'Product')


logger = logging.getLogger(__name__)


def get_product(sku):
    """Retrieve the product corresponding to the provided SKU."""
    try:
        return Product.objects.get(stockrecords__partner_sku=sku)
    except Product.DoesNotExist:
        raise exceptions.ProductNotFoundError(
            exceptions.PRODUCT_NOT_FOUND_DEVELOPER_MESSAGE.format(sku=sku)
        )


def get_order_metadata(basket):
    """Retrieve information required to place an order.

    Arguments:
        basket (Basket): The basket whose contents are to be ordered.

    Returns:
        dict: Containing an order number, a shipping method, a shipping charge,
            and a Price object representing the order total.
    """
    shipping_method = NoShippingRequired()
    shipping_charge = shipping_method.calculate(basket)
    total = OrderTotalCalculator().calculate(basket, shipping_charge)

    metadata = {
        AC.KEYS.ORDER_NUMBER: basket.order_number,
        AC.KEYS.SHIPPING_METHOD: shipping_method,
        AC.KEYS.SHIPPING_CHARGE: shipping_charge,
        AC.KEYS.ORDER_TOTAL: total,
    }

    return metadata


def get_lms_footer():
    """
    Retrieve LMS footer via branding API.

    Returns:
        str: HTML representation of the footer.
    """
    try:
        response = requests.get(
            get_lms_url('api/branding/v1/footer'),
            data={'language': 'en'}
        )
        if response.status_code == 200:
            return response.text
        else:
            logger.error(
                'Failed retrieve provider information for %s provider. Provider API returned status code %d. Error: %s',
                settings.LMS_URL_ROOT, response.status_code, response.text)
            return None
    except requests.exceptions.ConnectionError:
        logger.exception('Connection error occurred during getting data for %s provider', settings.LMS_URL_ROOT)
        return None
    except requests.Timeout:
        logger.exception('Failed to retrieve data for %s provider, connection timeout', settings.LMS_URL_ROOT)
        return None
