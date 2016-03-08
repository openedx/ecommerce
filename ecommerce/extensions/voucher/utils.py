"""Voucher Utility Methods. """
import base64
import datetime
import hashlib
import logging
import uuid
import pytz

from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model
from oscar.templatetags.currency_filters import currency

logger = logging.getLogger(__name__)

Benefit = get_model('offer', 'Benefit')
Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
CouponVouchers = get_model('voucher', 'CouponVouchers')
Product = get_model('catalogue', 'Product')
Range = get_model('offer', 'Range')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


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
        _('Name'),
        _('Code'),
        _('URL'),
        _('CourseID'),
        _('Price'),
        _('Invoiced Amount'),
        _('Discount'),
        _('Status'),
        _('Created By'),
        _('Create Date'),
        _('Expiry Date'),
    ]
    rows = []

    for coupon_voucher in coupon_vouchers:
        for voucher in coupon_voucher.vouchers.all():
            offer = voucher.offers.all().first()

            stockrecords = offer.condition.range.catalog.stock_records.all()
            course_seat = Product.objects.filter(id__in=[sr.product.id for sr in stockrecords]).first()
            seat_stockrecord = course_seat.stockrecords.first()
            history = coupon_voucher.coupon.history.latest()

            coupon_stockrecord = StockRecord.objects.get(product=coupon_voucher.coupon)
            course_id = course_seat.course.id
            price = currency(seat_stockrecord.price_excl_tax)
            invoiced_amount = currency(coupon_stockrecord.price_excl_tax)
            benefit_value = offer.benefit.value
            datetime_now = pytz.utc.localize(datetime.datetime.now())
            in_datetime_interval = (
                voucher.start_datetime < datetime_now and
                voucher.end_datetime > datetime_now
            )
            if in_datetime_interval:
                status = _('Redeemed') if voucher.num_orders > 0 else _('Active')
            else:
                status = _('Inactive')
            if offer.benefit.type == Benefit.PERCENTAGE:
                discount = _("{percentage} %").format(percentage=benefit_value)
            else:
                discount = currency(benefit_value)
            URL = '{}/coupons/redeem/?code={}'.format(settings.ECOMMERCE_URL_ROOT, voucher.code)
            author = history.history_user.full_name

            rows.append({
                'Name': voucher.name,
                'Code': voucher.code,
                'URL': URL,
                'CourseID': course_id,
                'Price': price,
                'Invoiced Amount': invoiced_amount,
                'Discount': discount,
                'Status': status,
                'Created By': author,
                'Create Date': voucher.start_datetime.strftime("%b %d,%y"),
                'Expiry Date': voucher.end_datetime.strftime("%b %d,%y"),
            })

    return field_names, rows


def _get_or_create_offer(product_range, benefit_type, benefit_value):
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

    offer_name = "Catalog [{}]-{}-{}".format(product_range.catalog.id, offer_benefit.type, offer_benefit.value)

    offer, __ = ConditionalOffer.objects.get_or_create(
        name=offer_name,
        offer_type=ConditionalOffer.VOUCHER,
        condition=offer_condition,
        benefit=offer_benefit,
    )
    return offer


def _generate_code_string(length):
    """
    Create a string of random characters of specified length

    Args:
        length (int): Defines the length of randomly generated string

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
        code=None):
    """
    Create vouchers

    Args:
            benefit_type (str): Type of benefit associated with vouchers.
            benefit_value (Decimal): Value of benefit associated with vouchers.
            catalog (Catalog): Catalog associated with range of products
                               to which a voucher can be applied to
            coupon (Coupon): Coupon entity associated with vouchers.
            end_datetime (datetime): End date for voucher offer
            name (str): Voucher name
            quantity (int): Number of vouchers to be created.
            start_datetime (datetime): Start date for voucher offer.
            voucher_type (str): Type of voucher.
            code (str): Code associated with vouchers. Defaults to None.

    Returns:
            List[Voucher]
    """

    logger.info("Creating [%d] vouchers catalog [%s]", quantity, catalog.id)

    vouchers = []

    range_name = (_('Range for {catalog_name}').format(catalog_name=catalog.name))
    product_range, __ = Range.objects.get_or_create(
        name=range_name,
        catalog=catalog,
    )

    offer = _get_or_create_offer(
        product_range=product_range,
        benefit_type=benefit_type,
        benefit_value=benefit_value
    )
    for __ in range(quantity):
        voucher = _create_new_voucher(
            coupon=coupon,
            end_datetime=end_datetime,
            offer=offer,
            start_datetime=start_datetime,
            voucher_type=voucher_type,
            code=code,
            name=name
        )
        vouchers.append(voucher)

    return vouchers


def get_voucher_discount_info(benefit, price):
    """
    Get discount info that will describe the effect that benefit has on product price

    Args:
        benefit (Benefit): Benefit provided by an applied voucher
        price (Decimal): Product price

    Returns:
        dict
    """

    if benefit and price > 0:
        if benefit.type == Benefit.PERCENTAGE:
            return {
                'discount_percentage': float(benefit.value),
                'is_discounted': True if benefit.value < 100 else False
            }
        else:
            discount_percentage = float(benefit.value / price) * 100.0
            return {
                'discount_percentage': 100.00 if discount_percentage > 100 else float(discount_percentage),
                'is_discounted': True if discount_percentage < 100 else False,
            }
    else:
        return {
            'discount_percentage': 0.00,
            'is_discounted': False
        }
