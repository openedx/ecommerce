import logging

from django.dispatch import receiver
from oscar.core.loading import get_class
import waffle

from ecommerce_worker.sailthru.v1.tasks import update_course_enrollment
from ecommerce.extensions.analytics.utils import silence_exceptions
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.utils import mode_for_seat


logger = logging.getLogger(__name__)
post_checkout = get_class('checkout.signals', 'post_checkout')
basket_addition = get_class('basket.signals', 'basket_addition')


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

    message_id = None
    if request:
        message_id = request.COOKIES.get('sailthru_bid')

    # loop through lines in order
    #  If multi product orders become common it may be worthwhile to pass an array of
    #  orders to the worker in one call to save overhead, however, that would be difficult
    #  because of the fact that there are different templates for free enroll versus paid enroll
    for line in order.lines.all():

        # get product
        product = line.product

        # get price
        price = line.line_price_excl_tax

        course_id = product.course_id

        # figure out course url
        course_url = _build_course_url(course_id)

        # pass event to ecommerce_worker.sailthru.v1.tasks to handle asynchronously
        update_course_enrollment.delay(order.user.email, course_url, False, mode_for_seat(product),
                                       unit_cost=price, course_id=course_id, currency=order.currency,
                                       site_code=order.site.siteconfiguration.partner.short_code,
                                       message_id=message_id)


@receiver(basket_addition)
@silence_exceptions("Failed to call Sailthru upon basket addition.")
def process_basket_addition(sender, product=None, user=None, request=None, **kwargs):  # pylint: disable=unused-argument
    """Tell Sailthru when payment started.

    Arguments:
            Parameters described at http://django-oscar.readthedocs.io/en/releases-1.1/ref/signals.html
    """

    if not waffle.switch_is_active('sailthru_enable'):
        return

    course_id = product.course_id

    # figure out course url
    course_url = _build_course_url(course_id)

    # get price & currency
    stock_record = product.stockrecords.first()
    if stock_record:
        price = stock_record.price_excl_tax
        currency = stock_record.price_currency

    # return if no price, no need to add free items to shopping cart
    if not price:
        return

    # pass event to ecommerce_worker.sailthru.v1.tasks to handle asynchronously
    update_course_enrollment.delay(user.email, course_url, True, mode_for_seat(product),
                                   unit_cost=price, course_id=course_id, currency=currency,
                                   site_code=request.site.siteconfiguration.partner.short_code,
                                   message_id=request.COOKIES.get('sailthru_bid'))


def _build_course_url(course_id):
    """Build a course url from a course id and the host"""
    return get_lms_url('courses/{}/info'.format(course_id))
