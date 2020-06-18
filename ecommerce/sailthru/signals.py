

import logging

import waffle
from django.dispatch import receiver
from ecommerce_worker.sailthru.v1.tasks import update_course_enrollment
from oscar.core.loading import get_class, get_model

from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.utils import mode_for_product
from ecommerce.extensions.analytics.utils import silence_exceptions

logger = logging.getLogger(__name__)
post_checkout = get_class('checkout.signals', 'post_checkout')
basket_addition = get_class('basket.signals', 'basket_addition')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
SAILTHRU_CAMPAIGN = 'sailthru_bid'


@receiver(post_checkout)
@silence_exceptions("Failed to call Sailthru upon order completion.")
def process_checkout_complete(sender, order=None, user=None, request=None,  # pylint: disable=unused-argument
                              response=None, **kwargs):  # pylint: disable=unused-argument
    """Tell Sailthru when payment done.

    Arguments:
            Parameters described at http://django-oscar.readthedocs.io/en/releases-1.1/ref/signals.html
    """

    if not waffle.switch_is_active('sailthru_enable'):
        return

    site_configuration = order.site.siteconfiguration
    if not site_configuration.enable_sailthru:
        return

    # get campaign id from cookies, or saved value in basket
    message_id = None
    if request:
        message_id = request.COOKIES.get('sailthru_bid')

    if not message_id:
        saved_id = BasketAttribute.objects.filter(
            basket=order.basket,
            attribute_type=get_basket_attribute_type()
        )
        if saved_id:
            message_id = saved_id[0].value_text

    # loop through lines in order
    #  If multi product orders become common it may be worthwhile to pass an array of
    #  orders to the worker in one call to save overhead, however, that would be difficult
    #  because of the fact that there are different templates for free enroll versus paid enroll
    lines = order.lines.all()
    # We are not sending multi product orders to sailthru for now, because
    # the abandoned cart email does not yet support baskets with multiple products
    if len(lines) > 1:
        return
    for line in lines:
        # get product
        product = line.product
        sku = line.partner_sku

        # ignore everything except course seats.  no support for coupons as of yet
        if product.is_seat_product:
            price = line.line_price_excl_tax
            course_id = product.course_id

            # Tell Sailthru that the purchase is complete asynchronously
            update_course_enrollment.delay(order.user.email, _build_course_url(course_id),
                                           False, mode_for_product(product),
                                           unit_cost=price, course_id=course_id, currency=order.currency,
                                           site_code=site_configuration.partner.short_code, message_id=message_id,
                                           sku=sku)


@receiver(basket_addition)
@silence_exceptions("Failed to call Sailthru upon basket addition.")
def process_basket_addition(sender, product=None, user=None, request=None, basket=None, is_multi_product_basket=None,
                            **kwargs):  # pylint: disable=unused-argument
    """Tell Sailthru when payment started.

    Arguments:
            Parameters described at http://django-oscar.readthedocs.io/en/releases-1.1/ref/signals.html
    """

    if not waffle.switch_is_active('sailthru_enable'):
        return

    site_configuration = request.site.siteconfiguration
    if not site_configuration.enable_sailthru:
        return

    # ignore everything except course seats.  no support for coupons as of yet
    if product.is_seat_product:
        course_id = product.course_id
        stock_record = product.stockrecords.first()
        if stock_record:
            price = stock_record.price_excl_tax
            currency = stock_record.price_currency

        # save Sailthru campaign ID, if there is one
        message_id = request.COOKIES.get('sailthru_bid')
        if message_id and basket:
            BasketAttribute.objects.update_or_create(
                basket=basket,
                attribute_type=get_basket_attribute_type(),
                defaults={'value_text': message_id}
            )

        # inform sailthru if there is a price.  The purpose of this call is to tell Sailthru when
        # an item has been added to the shopping cart so that an abandoned cart message can be sent
        # later if the purchase is not completed.  Abandoned cart support is only for purchases, not
        # for free enrolls
        if price and not is_multi_product_basket:
            update_course_enrollment.delay(user.email, _build_course_url(course_id), True, mode_for_product(product),
                                           unit_cost=price, course_id=course_id, currency=currency,
                                           site_code=site_configuration.partner.short_code, message_id=message_id)


def _build_course_url(course_id):
    """Build a course url from a course id and the host"""
    return get_lms_url('courses/{}/info'.format(course_id))


def get_basket_attribute_type():
    """ Returns `BasketAttributeType` for Sailthru campaign ID.

    Returns:
        BasketAttributeType
    """
    return BasketAttributeType.objects.get(name=SAILTHRU_CAMPAIGN)
