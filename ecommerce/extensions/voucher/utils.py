"""Voucher Utility Methods. """
from __future__ import unicode_literals

import base64
import datetime
import hashlib
import logging
import uuid
from decimal import Decimal, DecimalException

import dateutil.parser
import pytz
from django.conf import settings
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from edx_django_utils.cache import TieredCache
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from oscar.templatetags.currency_filters import currency

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.core.utils import log_message_and_raise_validation_error
from ecommerce.extensions.api import exceptions
from ecommerce.extensions.offer.models import OFFER_PRIORITY_VOUCHER
from ecommerce.extensions.offer.utils import get_discount_percentage, get_discount_value
from ecommerce.invoice.models import Invoice
from ecommerce.programs.conditions import ProgramCourseRunSeatsCondition
from ecommerce.programs.constants import BENEFIT_MAP
from ecommerce.programs.custom import class_path, create_condition

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


def _add_redemption_course_ids(new_row_to_append, header_row, redemption_course_ids):
    if any(row in [_('Catalog Query'), _('Program UUID')] for row in header_row):
        if len(redemption_course_ids) > 1:
            new_row_to_append[_('Redeemed For Course IDs')] = ', '.join(redemption_course_ids)
        else:
            new_row_to_append[_('Redeemed For Course ID')] = redemption_course_ids[0]


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
    created_date = coupon.date_updated.strftime("%b %d, %y") if coupon.date_updated else 'N/A'
    category_name = ProductCategory.objects.get(product=coupon).category.name

    try:
        note = coupon.attr.note
    except AttributeError:
        note = ''

    coupon_stockrecord = StockRecord.objects.get(product=coupon)
    invoiced_amount = currency(coupon_stockrecord.price_excl_tax)
    offer = voucher.offers.first()
    offer_range = offer.condition.range
    program_uuid = offer.condition.program_uuid
    benefit = offer.benefit

    if program_uuid:
        course_id = None
    elif offer_range.catalog:
        seat_stockrecord = offer_range.catalog.stock_records.first()
        course_id = seat_stockrecord.product.attr.course_key
        course_organization = CourseKey.from_string(course_id).org
    elif offer_range.catalog_query:
        catalog_query = offer_range.catalog_query
        course_id = None
        course_seat_types = offer_range.course_seat_types

    if course_id:
        price = currency(seat_stockrecord.price_excl_tax)
        discount_data = get_voucher_discount_info(benefit, seat_stockrecord.price_excl_tax)
        coupon_type, discount_percentage, discount_amount = _get_discount_info(discount_data)
    else:
        benefit_type = benefit.type or getattr(benefit.proxy(), 'benefit_class_type', None)

        if benefit_type == Benefit.PERCENTAGE:
            coupon_type = _('Discount') if benefit.value < 100 else _('Enrollment')
        else:
            coupon_type = None

        discount_percentage = _('{percentage} %').format(
            percentage=benefit.value) if benefit_type == Benefit.PERCENTAGE else None
        discount_amount = None
        price = None

    coupon_data = {
        _('Code'): _('This row applies to all vouchers'),
        _('Category'): category_name,
        _('Coupon Expiry Date'): voucher.end_datetime.strftime("%b %d, %y"),
        _('Coupon Name'): voucher.name,
        _('Coupon Start Date'): voucher.start_datetime.strftime("%b %d, %y"),
        _('Coupon Type'): coupon_type,
        _('Create Date'): created_date,
        _('Discount Percentage'): discount_percentage,
        _('Discount Amount'): discount_amount,
        _('Email Domains'): offer.email_domains,
        _('Invoiced Amount'): invoiced_amount,
        _('Note'): note,
        _('Price'): price
    }

    if course_id:
        coupon_data[_('Course ID')] = course_id
        coupon_data[_('Organization')] = course_organization
    elif program_uuid:
        coupon_data[_('Program UUID')] = program_uuid
    else:
        coupon_data[_('Catalog Query')] = catalog_query
        coupon_data[_('Course Seat Types')] = course_seat_types

    return coupon_data


def _get_voucher_info_for_coupon_report(voucher):
    offer = voucher.offers.first()
    status = _get_voucher_status(voucher, offer)
    path = '{path}?code={code}'.format(path=reverse('coupons:offer'), code=voucher.code)
    url = get_ecommerce_url(path)

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
        _('Code'): voucher.code,
        _('Maximum Coupon Usage'): max_uses_count,
        _('Redemption Count'): redemption_count,
        _('Status'): status,
        _('URL'): url
    }

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
        _('Code'),
        _('Coupon Name'),
        _('Maximum Coupon Usage'),
        _('Redemption Count'),
        _('Coupon Type'),
        _('URL'),
        _('Course ID'),
        _('Program UUID'),
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
        _('Redeemed For Course IDs'),
        _('Create Date'),
        _('Coupon Start Date'),
        _('Coupon Expiry Date'),
        _('Email Domains'),
    ]
    rows = []

    for coupon_voucher in coupon_vouchers:
        coupon = coupon_voucher.coupon
        client = Invoice.objects.get(order__lines__product=coupon).business_client.name
        rows.append(_get_info_for_coupon_report(coupon, coupon_voucher.vouchers.first()))
        rows[0][_('Client')] = client

        for voucher in coupon_voucher.vouchers.all().prefetch_related('offers'):
            row = _get_voucher_info_for_coupon_report(voucher)

            for item in (_('Order Number'), _('Redeemed By Username'),):
                row[item] = ''

            rows.append(row)

            if voucher.num_orders > 0:
                voucher_applications = VoucherApplication.objects.filter(
                    voucher=voucher).prefetch_related('user', 'order__lines')

                for application in voucher_applications:
                    redemption_course_ids = []
                    redemption_user_username = application.user.username

                    for line in application.order.lines.all():
                        redemption_course_ids.append(line.product.course_id)

                    new_row = row.copy()
                    _add_redemption_course_ids(new_row, rows[0], redemption_course_ids)
                    new_row.update({
                        _('Status'): _('Redeemed'),
                        _('Order Number'): application.order.number,
                        _('Redeemed By Username'): redemption_user_username,
                        _('Maximum Coupon Usage'): 1,
                        _('Redemption Count'): 1,
                    })
                    rows.append(new_row)

    if _('Program UUID') in rows[0]:
        field_names.remove(_('Course ID'))
        field_names.remove(_('Organization'))
        field_names.remove(_('Catalog Query'))
        field_names.remove(_('Course Seat Types'))
        field_names.remove(_('Redeemed For Course ID'))
    elif _('Catalog Query') in rows[0]:
        field_names.remove(_('Course ID'))
        field_names.remove(_('Organization'))
        field_names.remove(_('Program UUID'))
    else:
        field_names.remove(_('Catalog Query'))
        field_names.remove(_('Course Seat Types'))
        field_names.remove(_('Redeemed For Course ID'))
        field_names.remove(_('Redeemed For Course IDs'))
        field_names.remove(_('Program UUID'))

    return field_names, rows


def _get_or_create_offer(
        product_range, benefit_type, benefit_value, coupon_id=None,
        max_uses=None, offer_number=None, email_domains=None, program_uuid=None, site=None
):
    """
    Return an offer for a catalog with condition and benefit.

    If offer doesn't exist, new offer will be created and associated with
    provided Offer condition and benefit.

    Args:
        product_range (Range): Range of products associated with condition
        benefit_type (str): Type of benefit associated with the offer
        benefit_value (Decimal): Value of benefit associated with the offer
    Kwargs:
        coupon_id (int): ID of the coupon
        max_uses (int): number of maximum global application number an offer can have
        offer_number (int): number of the consecutive offer - used in case of a multiple
                            multi-use coupon
        email_domains (str): a comma-separated string of email domains allowed to apply
                            this offer
        program_uuid (str): the Program UUID
        site (site): Site for which the Coupon is created. Defaults to None.

    Returns:
        Offer
    """

    if program_uuid:
        try:
            offer_condition = ProgramCourseRunSeatsCondition.objects.get(program_uuid=program_uuid)
        except ProgramCourseRunSeatsCondition.DoesNotExist:
            offer_condition = create_condition(ProgramCourseRunSeatsCondition, program_uuid=program_uuid)
    else:
        offer_condition, __ = Condition.objects.get_or_create(
            range=product_range,
            type=Condition.COUNT,
            value=1,
        )
    try:
        if program_uuid:
            proxy_class = class_path(BENEFIT_MAP[benefit_type])
            offer_benefit = Benefit.objects.filter(proxy_class=proxy_class, value=benefit_value).first()

            if not offer_benefit:
                offer_benefit = Benefit()
                offer_benefit.proxy_class = proxy_class
                offer_benefit.value = benefit_value
                offer_benefit.save()

            offer_name = "Coupon [{}]-{}".format(coupon_id, offer_benefit.name)
        else:
            offer_benefit, __ = Benefit.objects.get_or_create(
                range=product_range,
                type=benefit_type,
                value=Decimal(benefit_value),
                max_affected_items=1,
            )
            offer_name = "Coupon [{}]-{}-{}".format(coupon_id, offer_benefit.type, offer_benefit.value)

    except (TypeError, DecimalException):  # If the benefit_value parameter is not sent TypeError will be raised
        log_message_and_raise_validation_error(
            'Failed to create Benefit. Benefit value must be a positive number or 0.'
        )

    if offer_number:
        offer_name = "{} [{}]".format(offer_name, offer_number)

    offer, __ = ConditionalOffer.objects.get_or_create(
        name=offer_name,
        offer_type=ConditionalOffer.VOUCHER,
        condition=offer_condition,
        benefit=offer_benefit,
        max_global_applications=max_uses,
        email_domains=email_domains,
        site=site,
        priority=OFFER_PRIORITY_VOUCHER,
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


def _create_new_voucher(code, end_datetime, name, offer, start_datetime, voucher_type):
    """
    Creates a voucher.

    If randomly generated voucher code already exists, new code will be generated and reverified.

    Args:
        code (str): Code associated with vouchers. If not provided, one will be generated.
        end_datetime (datetime): Voucher end date.
        name (str): Voucher name.
        offer (Offer): Offer associated with voucher.
        start_datetime (datetime): Voucher start date.
        voucher_type (str): Voucher usage.

    Returns:
        Voucher
    """
    if offer.benefit.type == Benefit.PERCENTAGE and offer.benefit.value == 100 and code:
        log_message_and_raise_validation_error('Failed to create Voucher. Code may not be set for enrollment coupon.')
    voucher_code = code or _generate_code_string(settings.VOUCHER_CODE_LENGTH)

    if not end_datetime:
        log_message_and_raise_validation_error('Failed to create Voucher. Voucher end datetime field must be set.')
    elif not isinstance(end_datetime, datetime.datetime):
        try:
            end_datetime = dateutil.parser.parse(end_datetime)
        except (AttributeError, ValueError, TypeError):
            log_message_and_raise_validation_error(
                'Failed to create Voucher. Voucher end datetime value [{date}] is invalid.'.format(date=end_datetime)
            )

    if not start_datetime:
        log_message_and_raise_validation_error('Failed to create Voucher. Voucher start datetime field must be set.')
    elif not isinstance(start_datetime, datetime.datetime):
        try:
            start_datetime = dateutil.parser.parse(start_datetime)
        except (AttributeError, ValueError, TypeError):
            log_message_and_raise_validation_error(
                'Failed to create Voucher. Voucher start datetime [{date}] is invalid.'.format(date=start_datetime)
            )

    voucher = Voucher.objects.create(
        name=name[:128],
        code=voucher_code,
        usage=voucher_type,
        start_datetime=start_datetime,
        end_datetime=end_datetime
    )
    voucher.offers.add(offer)

    return voucher


def create_vouchers(
        benefit_type,
        benefit_value,
        catalog,
        coupon,
        end_datetime,
        enterprise_customer,
        enterprise_customer_catalog,
        name,
        quantity,
        start_datetime,
        voucher_type,
        code=None,
        max_uses=None,
        _range=None,
        catalog_query=None,
        course_seat_types=None,
        email_domains=None,
        course_catalog=None,
        program_uuid=None,
        site=None,
):
    """
    Create vouchers.

    Arguments:
        benefit_type (str): Type of benefit associated with vouchers.
        benefit_value (Decimal): Value of benefit associated with vouchers.
        catalog (Catalog): Catalog associated with range of products
                           to which a voucher can be applied to.
        catalog_query (str): ElasticSearch query used by dynamic coupons. Defaults to None.
        code (str): Code associated with vouchers. Defaults to None.
        coupon (Coupon): Coupon entity associated with vouchers.
        course_catalog (int): Course catalog id from Discovery Service. Defaults to None.
        course_seat_types (str): Comma-separated list of course seat types.
        email_domains (str): List of email domains to restrict coupons. Defaults to None.
        end_datetime (datetime): End date for voucher offer.
        enterprise_customer (str): UUID of an EnterpriseCustomer attached to this voucher
        enterprise_customer_catalog (str): UUID of an EnterpriseCustomerCatalog attached to this voucher
        max_uses (int): Number of Voucher max uses. Defaults to None.
        name (str): Voucher name.
        quantity (int): Number of vouchers to be created.
        start_datetime (datetime): Start date for voucher offer.
        voucher_type (str): Type of voucher.
        _range (Range): Product range. Defaults to None.
        program_uuid (str): Program UUID. Defaults to None.
        site (site): Site for which the Coupon is created. Defaults to None.

    Returns:
        List[Voucher]
    """
    logger.info("Creating [%d] vouchers product [%s]", quantity, coupon.id)
    vouchers = []
    offers = []

    # Maximum number of uses can be set for each voucher type and disturb
    # the predefined behaviours of the different voucher types. Therefor
    # here we enforce that the max_uses variable can't be used for SINGLE_USE
    # voucher types.
    if max_uses is not None:
        if voucher_type == Voucher.SINGLE_USE:
            log_message_and_raise_validation_error(
                'Failed to create Voucher. max_uses field cannot be set for voucher type [{voucher_type}].'.format(
                    voucher_type=Voucher.SINGLE_USE
                )
            )
        try:
            max_uses = int(max_uses)
        except ValueError:
            raise log_message_and_raise_validation_error('Failed to create Voucher. max_uses field must be a number.')

    if _range:
        # Enrollment codes use a custom range.
        logger.info("Creating [%d] enrollment code vouchers", quantity)
        product_range = _range
    else:
        logger.info("Creating [%d] vouchers for coupon [%s]", quantity, coupon.id)
        range_name = (_('Range for coupon [{coupon_id}]').format(coupon_id=coupon.id))
        # make sure course catalog is None if its empty
        course_catalog = course_catalog if course_catalog else None
        # make sure enterprise_customer is None if it's empty
        enterprise_customer = enterprise_customer or None
        enterprise_customer_catalog = enterprise_customer_catalog or None
        # we do not need a range if this is for a Program
        if program_uuid:
            product_range = None
        else:
            product_range, __ = Range.objects.get_or_create(
                name=range_name,
                catalog=catalog,
                catalog_query=catalog_query,
                course_catalog=course_catalog,
                course_seat_types=course_seat_types,
                enterprise_customer=enterprise_customer,
                enterprise_customer_catalog=enterprise_customer_catalog,
            )

    # In case of more than 1 multi-usage coupon, each voucher needs to have an individual
    # offer because the usage is tied to the offer so that a usage on one voucher would
    # mean all vouchers will have their usage decreased by one, hence each voucher needs
    # its own offer to keep track of its own usages without interfering with others.
    multi_offer = True if (
        voucher_type == Voucher.MULTI_USE or voucher_type == Voucher.ONCE_PER_CUSTOMER
    ) else False
    num_of_offers = quantity if multi_offer else 1
    for num in range(num_of_offers):
        offer = _get_or_create_offer(
            product_range=product_range,
            benefit_type=benefit_type,
            benefit_value=benefit_value,
            max_uses=max_uses,
            coupon_id=coupon.id,
            offer_number=num,
            email_domains=email_domains,
            program_uuid=program_uuid,
            site=site
        )
        offers.append(offer)

    for i in range(quantity):
        voucher = _create_new_voucher(
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
                'discount_value': get_discount_value(discount_percentage=benefit_value, product_price=price),
                'is_discounted': True if benefit.value < 100 else False
            }
        else:
            discount_percentage = get_discount_percentage(discount_value=benefit_value, product_price=price)
            if discount_percentage > 100:
                discount_percentage = 100.00
                discount_value = price
            else:
                discount_percentage = discount_percentage
                discount_value = benefit_value
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


def update_voucher_offer(offer, benefit_value, benefit_type, coupon, max_uses=None,
                         email_domains=None, program_uuid=None):
    """
    Update voucher offer with new benefit value.

    Args:
        offer (Offer): Offer associated with a voucher.
        benefit_value (Decimal): Value of benefit associated with vouchers.
        benefit_type (str): Type of benefit associated with vouchers.
        coupon (Product): The coupon whos offer(s) is updated.

    Kwargs:
        max_uses (int): number of maximum global application number an offer can have.
        email_domains (str): a comma-separated string of email domains allowed to apply
                            this offer.
        program_uuid (str): Program UUID

    Returns:
        Offer
    """
    return _get_or_create_offer(
        product_range=offer.benefit.range,
        benefit_value=benefit_value,
        benefit_type=benefit_type,
        coupon_id=coupon.id,
        max_uses=max_uses,
        email_domains=email_domains,
        program_uuid=program_uuid
    )


def get_cached_voucher(code):
    """
    Returns a voucher from cache if one is stored to cache, if not the voucher
    is retrieved from database and stored to cache.

    Arguments:
        code (str): The code of a coupon voucher.

    Returns:
        voucher (Voucher): The Voucher for the passed code.

    Raises:
        Voucher.DoesNotExist: When no vouchers with provided code exist.
    """
    voucher_code = 'voucher_{code}'.format(code=code)
    cache_key = hashlib.md5(voucher_code).hexdigest()
    voucher_cached_response = TieredCache.get_cached_response(cache_key)
    if voucher_cached_response.is_found:
        return voucher_cached_response.value

    voucher = Voucher.objects.get(code=code)

    TieredCache.set_all_tiers(cache_key, voucher, settings.VOUCHER_CACHE_TIMEOUT)
    return voucher


def get_voucher_and_products_from_code(code):
    """
    Returns a voucher and product for a given code.

    Arguments:
        code (str): The code of a coupon voucher.

    Returns:
        voucher (Voucher): The Voucher for the passed code.
        products (list): List of Products associated with the Voucher.

    Raises:
        Voucher.DoesNotExist: When no vouchers with provided code exist.
        ProductNotFoundError: When no products are associated with the voucher.
    """
    voucher = get_cached_voucher(code)
    voucher_range = voucher.offers.first().benefit.range
    products = voucher_range.all_products()

    if products or voucher_range.catalog_query or voucher_range.course_catalog:
        # List of products is empty in case of Multi-course coupon
        return voucher, products
    else:
        raise exceptions.ProductNotFoundError()
