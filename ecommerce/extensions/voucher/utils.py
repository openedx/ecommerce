"""Voucher Utility Methods. """
import base64
import datetime
import hashlib
import logging
import uuid
import pytz

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model
from oscar.templatetags.currency_filters import currency
from edx_rest_api_client.client import EdxRestApiClient

from ecommerce.core.url_utils import get_ecommerce_url, get_lms_url
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
        _('Coupon Type'),
        _('URL'),
        _('CourseID'),
        _('Partner'),
        _('Client'),
        _('Category'),
        _('Note'),
        _('Price'),
        _('Invoiced Amount'),
        _('Discount Percentage'),
        _('Discount Amount'),
        _('Status'),
        _('Redeemed By ID'),
        _('Redeemed By Username'),
        _('Created By'),
        _('Create Date'),
        _('Coupon Start Date'),
        _('Coupon Expiry Date'),
    ]
    rows = []

    for coupon_voucher in coupon_vouchers:
        coupon = coupon_voucher.coupon

        # Get client based on the invoice that was created during coupon creation
        basket = Basket.objects.filter(lines__product_id=coupon.id).first()
        try:
            order = get_object_or_404(Order, basket=basket)
            invoice = get_object_or_404(Invoice, order=order)
            client = invoice.client.name
        except Http404:
            client = basket.owner.username

        for voucher in coupon_voucher.vouchers.all():
            offer = voucher.offers.all().first()

            stockrecords = offer.condition.range.catalog.stock_records.all()
            course_seat = Product.objects.filter(id__in=[sr.product.id for sr in stockrecords]).first()
            seat_stockrecord = course_seat.stockrecords.first()
            history = coupon.history.latest()

            coupon_stockrecord = StockRecord.objects.get(product=coupon)
            course_id = course_seat.course.id
            api = EdxRestApiClient(get_lms_url('api/courses/v1/'))
            course_organization = api.courses(course_id).get()['org']

            price = currency(seat_stockrecord.price_excl_tax)
            invoiced_amount = currency(coupon_stockrecord.price_excl_tax)
            datetime_now = pytz.utc.localize(datetime.datetime.now())
            in_datetime_interval = (
                voucher.start_datetime < datetime_now and
                voucher.end_datetime > datetime_now
            )
            discount_data = get_voucher_discount_info(offer.benefit, seat_stockrecord.price_excl_tax)
            coupon_type = _('Discount') if discount_data['is_discounted'] else _('Enrollment')
            if in_datetime_interval:
                status = _('Redeemed') if voucher.num_orders > 0 else _('Active')
            else:
                status = _('Inactive')

            discount_percentage = _("{percentage} %").format(percentage=discount_data['discount_percentage'])
            discount_amount = currency(discount_data['discount_value'])

            if voucher.num_orders > 0:
                voucher_applications = VoucherApplication.objects.filter(voucher=voucher).all()
                redemption_users = [application.user for application in voucher_applications]
                redemption_user_ids = ', '.join([str(user.id) for user in redemption_users])
                redemption_user_usernames = ', '.join([user.username for user in redemption_users])
            else:
                redemption_user_ids = redemption_user_usernames = ''

            URL = '{url}?code={code}'.format(url=get_ecommerce_url('/coupons/offer/'), code=voucher.code)
            author = history.history_user.full_name

            try:
                note = coupon.attr.note
            except AttributeError:
                note = ''

            try:
                category = get_object_or_404(ProductCategory, product=coupon).category.name
            except Http404:
                category = ""

            rows.append({
                'Coupon Name': voucher.name,
                'Code': voucher.code,
                'Coupon Type': coupon_type,
                'URL': URL,
                'CourseID': course_id,
                'Partner': course_organization,
                'Client': client,
                'Category': category,
                'Note': note,
                'Price': price,
                'Invoiced Amount': invoiced_amount,
                'Discount Percentage': discount_percentage,
                'Discount Amount': discount_amount,
                'Status': status,
                'Redeemed By ID': redemption_user_ids,
                'Redeemed By Username': redemption_user_usernames,
                'Created By': author,
                'Create Date': history.history_date.strftime("%b %d,%y"),
                'Coupon Start Date': voucher.start_datetime.strftime("%b %d,%y"),
                'Coupon Expiry Date': voucher.end_datetime.strftime("%b %d,%y"),
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
