

import logging

import waffle
from django.dispatch import receiver
from oscar.core.loading import get_class, get_model

from ecommerce.courses.utils import mode_for_product
from ecommerce.extensions.analytics.utils import silence_exceptions, track_segment_event
from ecommerce.extensions.checkout.utils import get_credit_provider_details, get_receipt_page_url
from ecommerce.notifications.notifications import send_notification
from ecommerce.programs.utils import get_program

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
BUNDLE = 'bundle_identifier'
logger = logging.getLogger(__name__)
post_checkout = get_class('checkout.signals', 'post_checkout')

# Number of orders currently supported for the email notifications
ORDER_LINE_COUNT = 1


@receiver(post_checkout, dispatch_uid='tracking.post_checkout_callback')
@silence_exceptions('Failed to emit tracking event upon order completion.')
def track_completed_order(sender, order=None, **kwargs):  # pylint: disable=unused-argument
    """
    Emit a tracking event when
    1. An order is placed OR
    2. An enrollment code purchase order is placed.
    """
    if order.total_excl_tax <= 0:
        return

    properties = {
        'orderId': order.number,
        'total': str(order.total_excl_tax),
        # For Rockerbox integration, we need a field named revenue since they cannot parse a field named total.
        # TODO: DE-1188: Remove / move Rockerbox integration code.
        'revenue': str(order.total_excl_tax),
        'currency': order.currency,
        'discount': str(order.total_discount_incl_tax),
        'products': [
            {
                # For backwards-compatibility with older events the `sku` field is (ab)used to
                # store the product's `certificate_type`, while the `id` field holds the product's
                # SKU. Marketing is aware that this approach will not scale once we start selling
                # products other than courses, and will need to change in the future.
                'id': line.partner_sku,
                'sku': mode_for_product(line.product),
                'name': line.product.course.id if line.product.course else line.product.title,
                'price': str(line.line_price_excl_tax),
                'quantity': line.quantity,
                'category': line.product.get_product_class().name,
            } for line in order.lines.all()
        ],
    }
    if order.user:
        properties['email'] = order.user.email

    for line in order.lines.all():
        if line.product.is_enrollment_code_product:
            # Send analytics events to track bulk enrollment code purchases.
            track_segment_event(order.site, order.user, 'Bulk Enrollment Codes Order Completed', properties)
            return

        if line.product.is_coupon_product:
            return

    voucher = order.basket_discounts.filter(voucher_id__isnull=False).first()
    coupon = voucher.voucher_code if voucher else None
    properties['coupon'] = coupon

    try:
        bundle_id = BasketAttribute.objects.get(basket=order.basket, attribute_type__name=BUNDLE).value_text
        program = get_program(bundle_id, order.basket.site.siteconfiguration)
        if len(order.lines.all()) < len(program.get('courses')):
            variant = 'partial'
        else:
            variant = 'full'
        bundle_product = {
            'id': bundle_id,
            'price': '0',
            'quantity': str(len(order.lines.all())),
            'category': 'bundle',
            'variant': variant,
            'name': program.get('title')
        }
        properties['products'].append(bundle_product)
    except BasketAttribute.DoesNotExist:
        logger.info('There is no program or bundle associated with order number %s', order.number)

    track_segment_event(order.site, order.user, 'Order Completed', properties)


@receiver(post_checkout, dispatch_uid='send_completed_order_email')
@silence_exceptions("Failed to send order completion email.")
def send_course_purchase_email(sender, order=None, request=None, **kwargs):  # pylint: disable=unused-argument
    """
    Send seat purchase notification email
    """
    if waffle.switch_is_active('ENABLE_NOTIFICATIONS'):
        if len(order.lines.all()) != ORDER_LINE_COUNT:
            logger.info('Currently support receipt emails for order with one item.')
            return

        product = order.lines.first().product
        if product.is_seat_product or product.is_course_entitlement_product:
            recipient = request.POST.get('req_bill_to_email', order.user.email) if request else order.user.email
            receipt_page_url = get_receipt_page_url(
                order_number=order.number,
                site_configuration=order.site.siteconfiguration
            )
            credit_provider_id = getattr(product.attr, 'credit_provider', None)
            if credit_provider_id:
                provider_data = get_credit_provider_details(
                    credit_provider_id=credit_provider_id,
                    site_configuration=order.site.siteconfiguration
                )

                if provider_data:
                    send_notification(
                        order.user,
                        'CREDIT_RECEIPT',
                        {
                            'course_title': product.title,
                            'receipt_page_url': receipt_page_url,
                            'credit_hours': product.attr.credit_hours,
                            'credit_provider': provider_data['display_name'],
                        },
                        order.site,
                        recipient
                    )
            elif getattr(product.attr, 'certificate_type', None) == 'credit':
                logger.error(
                    'Failed to send credit receipt notification. Credit seat product [%s] has no provider.', product.id
                )
            elif order.basket.total_incl_tax != 0:
                send_notification(
                    order.user,
                    'COURSE_PURCHASED',
                    {
                        'course_title': product.title,
                        'receipt_page_url': receipt_page_url,
                    },
                    order.site,
                    recipient
                )
