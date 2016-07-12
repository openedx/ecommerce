"""Voucher Utility Methods. """
import base64
import datetime
import hashlib
import logging
import uuid

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from oscar.templatetags.currency_filters import currency
import pytz

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)

Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
CouponVouchers = get_model('voucher', 'CouponVouchers')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
Range = get_model('offer', 'Range')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
VoucherApplication = get_model('voucher', 'VoucherApplication')


def _get_voucher_status(voucher, offer):
    """Retrieve the status of a voucher.

    Arguments:
        voucher(Voucher)
        offer(Offer)

    Returns
        status(translate string object)
    """

    datetime_now = datetime.datetime.now(pytz.UTC)
    not_expired = (
        voucher.start_datetime < datetime_now and
        voucher.end_datetime > datetime_now
    )
    if not_expired:
        status = _('Redeemed') if not offer.is_available() else _('Active')
    else:
        status = _('Inactive')

    return status


def _get_discount_info(discount_data):
    """Retrieve voucher discount info.

    Arguments:
        discount_data (dict)

    Returns
        coupon_type (str)
        discount_amount (str)
        discount_percentage (str)
    """
    if discount_data:
        coupon_type = _('Discount') if discount_data['is_discounted'] else _('Enrollment')
        discount_percentage = _("{percentage} %").format(percentage=discount_data['discount_percentage'])
        discount_amount = currency(discount_data['discount_value'])
        return coupon_type, discount_percentage, discount_amount
    logger.warning('Unable to get voucher discount info. Discount data not provided.')
    return None, None, None


def _get_info_for_coupon_report(coupon, voucher):
    offer = voucher.offers.all().first()
    if offer.condition.range.catalog:
        coupon_stockrecord = StockRecord.objects.get(product=coupon)
        invoiced_amount = currency(coupon_stockrecord.price_excl_tax)
        seat_stockrecord = offer.condition.range.catalog.stock_records.first()
        course_id = seat_stockrecord.product.attr.course_key
        course_organization = CourseKey.from_string(course_id).org
        price = currency(seat_stockrecord.price_excl_tax)
        discount_data = get_voucher_discount_info(offer.benefit, seat_stockrecord.price_excl_tax)
    else:
        # Note (multi-courses): Need to account for multiple seats.
        catalog_query = offer.condition.range.catalog_query
        course_seat_types = offer.condition.range.course_seat_types
        course_id = None
        coupon_stockrecord = None
        invoiced_amount = None
        seat_stockrecord = None
        course_organization = None
        price = None
        discount_data = None

    history = coupon.history.first()
    coupon_type, discount_percentage, discount_amount = _get_discount_info(discount_data)
    status = _get_voucher_status(voucher, offer)
    path = '{path}?code={code}'.format(path=reverse('coupons:offer'), code=voucher.code)
    url = get_ecommerce_url(path)
    author = history.history_user.full_name.encode('utf8')

    try:
        note = coupon.attr.note.encode('utf8')
    except AttributeError:
        note = ''

    product_categories = ProductCategory.objects.filter(product=coupon)
    if product_categories:
        category_names = ', '.join([pc.category.name for pc in product_categories])
    else:
        category_names = ''

    # Set the max_uses_count for single-use vouchers to 1,
    # for other usage limitations (once per customer and multi-use)
    # which don't have the max global applications limit set,
    # set the max_uses_count to 10000 which is the arbitrary limit Oscar sets:
    # https://github.com/django-oscar/django-oscar/blob/master/src/oscar/apps/offer/abstract_models.py#L253
    redemption_count = offer.num_applications
    if voucher.usage == Voucher.SINGLE_USE:
        max_uses_count = 1
        redemption_count = voucher.num_orders
    elif voucher.usage != Voucher.SINGLE_USE and offer.max_global_applications is None:
        max_uses_count = 10000
    else:
        max_uses_count = offer.max_global_applications

    coupon_data = {
        'Coupon Name': voucher.name.encode('utf8'),
        'Code': voucher.code,
        'Coupon Type': coupon_type,
        'URL': url,
        'Category': category_names,
        'Note': note,
        'Price': price,
        'Invoiced Amount': invoiced_amount,
        'Discount Percentage': discount_percentage,
        'Discount Amount': discount_amount,
        'Status': status,
        'Created By': author,
        'Create Date': history.history_date.strftime("%b %d, %y"),
        'Coupon Start Date': voucher.start_datetime.strftime("%b %d, %y"),
        'Coupon Expiry Date': voucher.end_datetime.strftime("%b %d, %y"),
        'Maximum Coupon Usage': max_uses_count,
        'Redemption Count': redemption_count,
    }

    if course_id:
        coupon_data['Course ID'] = course_id
        coupon_data['Organization'] = course_organization
    else:
        coupon_data['Catalog Query'] = catalog_query
        coupon_data['Course Seat Types'] = course_seat_types

    return coupon_data


def generate_coupon_report(coupon_vouchers):
    """
    Generate coupon report data

    Args:
        coupon_vouchers (List[CouponVouchers]): List of coupon_vouchers the report should be generated for

    Returns:
        List[str]
        List[dict]
    """

    field_names = [
        _('Coupon Name'),
        _('Code'),
        _('Maximum Coupon Usage'),
        _('Redemption Count'),
        _('Coupon Type'),
        _('URL'),
        _('Course ID'),
        _('Catalog Query'),
        _('Course Seat Types'),
        _('Organization'),
        _('Client'),
        _('Category'),
        _('Note'),
        _('Price'),
        _('Invoiced Amount'),
        _('Discount Percentage'),
        _('Discount Amount'),
        _('Status'),
        _('Order Number'),
        _('Redeemed By Username'),
        _('Redeemed For Course ID'),
        _('Created By'),
        _('Create Date'),
        _('Coupon Start Date'),
        _('Coupon Expiry Date'),
    ]
    rows = []

    for coupon_voucher in coupon_vouchers:
        coupon = coupon_voucher.coupon
        client = Invoice.objects.get(order__basket__lines__product=coupon).business_client.name

        for voucher in coupon_voucher.vouchers.all():
            row = _get_info_for_coupon_report(coupon, voucher)

            for item in ('Order Number', 'Redeemed By Username',):
                row[item] = ''

            row['Client'] = client.encode('utf8')
            rows.append(row)
            if voucher.num_orders > 0:
                voucher_applications = VoucherApplication.objects.filter(voucher=voucher)
                for application in voucher_applications:
                    redemption_user_username = application.user.username
                    redemption_course_id = application.order.lines.first().product.course_id

                    new_row = row.copy()

                    if 'Catalog Query' in new_row:
                        new_row['Redeemed For Course ID'] = redemption_course_id

                    new_row.update({
                        'Status': _('Redeemed'),
                        'Order Number': application.order.number,
                        'Redeemed By Username': redemption_user_username,
                        'Maximum Coupon Usage': 1,
                        'Redemption Count': 1,
                    })

                    rows.append(new_row)

    if 'Catalog Query' in rows[0]:
        field_names.remove('Course ID')
        field_names.remove('Organization')
    else:
        field_names.remove('Catalog Query')
        field_names.remove('Course Seat Types')
        field_names.remove('Redeemed For Course ID')

    return field_names, rows


def _get_or_create_offer(
        product_range, benefit_type, benefit_value, coupon_id=None, max_uses=None, offer_number=None
):
    """
    Return an offer for a catalog with condition and benefit.

    If offer doesn't exist, new offer will be created and associated with
    provided Offer condition and benefit.

    Args:
        product_range (Range): Range of products associated with condition
        benefit_type (str): Type of benefit associated with the offer
        benefit_value (Decimal): Value of benefit associated with the offer

    Returns:
        Offer
    """
    offer_condition, __ = Condition.objects.get_or_create(
        range=product_range,
        type=Condition.COUNT,
        value=1,
    )
    offer_benefit, __ = Benefit.objects.get_or_create(
        range=product_range,
        type=benefit_type,
        value=benefit_value,
        max_affected_items=1,
    )

    offer_name = "Coupon [{}]-{}-{}".format(coupon_id, offer_benefit.type, offer_benefit.value)
    if offer_number:
        offer_name = "{} [{}]".format(offer_name, offer_number)

    offer, __ = ConditionalOffer.objects.get_or_create(
        name=offer_name,
        offer_type=ConditionalOffer.VOUCHER,
        condition=offer_condition,
        benefit=offer_benefit,
        max_global_applications=max_uses
    )

    return offer


def _generate_code_string(length):
    """
    Create a string of random characters of specified length

    Args:
        length (int): Defines the length of randomly generated string.

    Raises:
        ValueError raised if length is less than one.

    Returns:
        str
    """
    if length < 1:
        raise ValueError("Voucher code length must be a positive number.")

    h = hashlib.sha256()
    h.update(uuid.uuid4().get_bytes())
    voucher_code = base64.b32encode(h.digest())[0:length]
    if Voucher.objects.filter(code__iexact=voucher_code).exists():
        return _generate_code_string(length)

    return voucher_code


def _create_new_voucher(code, coupon, end_datetime, name, offer, start_datetime, voucher_type):
    """
    Creates a voucher.

    If randomly generated voucher code already exists, new code will be generated and reverified.

    Args:
        code (str): Code associated with vouchers. If not provided, one will be generated.
        coupon (Product): Coupon product associated with voucher.
        end_datetime (datetime): Voucher end date.
        name (str): Voucher name.
        offer (Offer): Offer associated with voucher.
        start_datetime (datetime): Voucher start date.
        voucher_type (str): Voucher usage.

    Returns:
        Voucher
    """
    voucher_code = code or _generate_code_string(settings.VOUCHER_CODE_LENGTH)

    voucher = Voucher.objects.create(
        name=name,
        code=voucher_code,
        usage=voucher_type,
        start_datetime=start_datetime,
        end_datetime=end_datetime
    )
    voucher.offers.add(offer)

    coupon_voucher, __ = CouponVouchers.objects.get_or_create(coupon=coupon)
    coupon_voucher.vouchers.add(voucher)

    return voucher


def create_vouchers(
        benefit_type,
        benefit_value,
        catalog,
        coupon,
        end_datetime,
        name,
        quantity,
        start_datetime,
        voucher_type,
        code=None,
        max_uses=None,
        _range=None,
        catalog_query=None,
        course_seat_types=None):
    """
    Create vouchers.

    Args:
            benefit_type (str): Type of benefit associated with vouchers.
            benefit_value (Decimal): Value of benefit associated with vouchers.
            catalog (Catalog): Catalog associated with range of products
                               to which a voucher can be applied to.
            coupon (Coupon): Coupon entity associated with vouchers.
            end_datetime (datetime): End date for voucher offer.
            name (str): Voucher name.
            quantity (int): Number of vouchers to be created.
            start_datetime (datetime): Start date for voucher offer.
            voucher_type (str): Type of voucher.
            code (str): Code associated with vouchers. Defaults to None.

    Returns:
            List[Voucher]
    """
    logger.info("Creating [%d] vouchers product [%s]", quantity, coupon.id)
    vouchers = []
    offers = []

    if _range:
        # Enrollment codes use a custom range.
        logger.info("Creating [%d] enrollment code vouchers", quantity)
        product_range = _range
    else:
        logger.info("Creating [%d] vouchers for coupon [%s]", quantity, coupon.id)
        range_name = (_('Range for coupon [{coupon_id}]').format(coupon_id=coupon.id))
        product_range, __ = Range.objects.get_or_create(
            name=range_name,
            catalog=catalog,
            catalog_query=catalog_query,
            course_seat_types=course_seat_types
        )

    # In case of more than 1 multi-usage coupon, each voucher needs to have an individual
    # offer because the usage is tied to the offer so that a usage on one voucher would
    # mean all vouchers will have their usage decreased by one, hence each voucher needs
    # it's own offer to keep track of it's own usages without interfering with others.
    multi_offer = True if quantity > 1 and max_uses > 1 else False
    num_of_offers = quantity if multi_offer else 1
    for num in range(num_of_offers):
        offer = _get_or_create_offer(
            product_range=product_range,
            benefit_type=benefit_type,
            benefit_value=benefit_value,
            max_uses=max_uses,
            coupon_id=coupon.id,
            offer_number=num
        )
        offers.append(offer)

    for i in range(quantity):
        voucher = _create_new_voucher(
            coupon=coupon,
            end_datetime=end_datetime,
            offer=offers[i] if multi_offer else offers[0],
            start_datetime=start_datetime,
            voucher_type=voucher_type,
            code=code,
            name=name
        )
        vouchers.append(voucher)

    return vouchers


def get_voucher_discount_info(benefit, price):
    """
    Get discount info that will describe the effect that benefit has on product price.

    Args:
        benefit (Benefit): Benefit provided by an applied voucher.
        price (Decimal): Product price.

    Returns:
        dict
    """

    if benefit and price > 0:
        benefit_value = float(benefit.value)
        price = float(price)
        if benefit.type == Benefit.PERCENTAGE:
            return {
                'discount_percentage': benefit_value,
                'discount_value': benefit_value * price / 100.0,
                'is_discounted': True if benefit.value < 100 else False
            }
        else:
            discount_percentage = benefit_value / price * 100.0
            if discount_percentage > 100:
                discount_percentage = 100.00
                discount_value = price
            else:
                discount_percentage = float(discount_percentage)
                discount_value = benefit.value
            return {
                'discount_percentage': discount_percentage,
                'discount_value': float(discount_value),
                'is_discounted': True if discount_percentage < 100 else False,
            }
    else:
        return {
            'discount_percentage': 0.00,
            'discount_value': 0.00,
            'is_discounted': False
        }


def update_voucher_offer(offer, benefit_value, benefit_type, coupon, max_uses=None):
    """
    Update voucher offer with new benefit value.

    Args:
        offer (Offer): Offer associated with a voucher.
        benefit_value (Decimal): Value of benefit associated with vouchers.
        benefit_type (str): Type of benefit associated with vouchers.

    Returns:
        Offer
    """
    return _get_or_create_offer(
        product_range=offer.benefit.range,
        benefit_value=benefit_value,
        benefit_type=benefit_type,
        coupon_id=coupon.id,
        max_uses=max_uses
    )
