

import logging
from hashlib import md5

from django.conf import settings
from django.db.utils import IntegrityError
from oscar.core.loading import get_model

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.extensions.payment.models import EnterpriseContractMetadata
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.extensions.voucher.utils import create_vouchers

Catalog = get_model('catalogue', 'Catalog')
logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')


def create_coupon_product(
        benefit_type,
        benefit_value,
        catalog,
        catalog_query,
        category,
        code,
        course_seat_types,
        email_domains,
        end_datetime,
        enterprise_customer,
        enterprise_customer_catalog,
        max_uses,
        note,
        partner,
        price,
        quantity,
        start_datetime,
        title,
        voucher_type,
        course_catalog,
        program_uuid,
        site,
        salesforce_opportunity_line_item,
        sales_force_id=None,
):
    """
    Creates a coupon product and a stock record for it.

    Arguments:
        benefit_type (str): Voucher Benefit type.
        benefit_value (int): Voucher Benefit value.
        catalog (Catalog): Catalog used to create a range of products.
        catalog_query (str): ElasticSearch query used by dynamic coupons.
        category (dict): Contains category ID and name.
        code (str): Voucher code.
        course_seat_types (str): Comma-separated list of course seat types.
        course_catalog (int): Course catalog id from Discovery Service
        email_domains (str): Comma-separated list of email domains.
        end_datetime (Datetime): Voucher end Datetime.
        enterprise_customer (str): UUID of an EnterpriseCustomer to attach to this voucher
        enterprise_customer_catalog (str): UUID of an EnterpriseCustomerCatalog to attach to this voucher
        max_uses (int): Number of Voucher max uses.
        note (str): Coupon note.
        partner (User): Partner associated with coupon Stock Record.
        price (int): The price of the coupon.
        quantity (int): Number of vouchers to be created and associated with the coupon.
        start_datetime (Datetime): Voucher start Datetime.
        title (str): The name of the coupon.
        voucher_type (str): Voucher type
        program_uuid (str): Program UUID for the Coupon
        site (site): Site for which the Coupon is created.
        sales_force_id (str): Sales Force Opprtunity ID
        salesforce_opportunity_line_item (str): Sales Force Opportunity Line Item ID

    Returns:
        A coupon Product object.

    Raises:
        IntegrityError: An error occurred when create_vouchers method returns
                        an IntegrityError exception
    """
    coupon_product = create_coupon_product_and_stockrecord(title, category, partner, price)

    # Vouchers are created during order and not fulfillment like usual
    # because we want vouchers to be part of the line in the order.

    try:
        vouchers = create_vouchers(
            benefit_type=benefit_type,
            benefit_value=benefit_value,
            catalog=catalog,
            catalog_query=catalog_query,
            code=code or None,
            coupon=coupon_product,
            course_catalog=course_catalog,
            course_seat_types=course_seat_types,
            email_domains=email_domains,
            end_datetime=end_datetime,
            enterprise_customer=enterprise_customer,
            enterprise_customer_catalog=enterprise_customer_catalog,
            max_uses=max_uses,
            name=title,
            quantity=int(quantity),
            start_datetime=start_datetime,
            voucher_type=voucher_type,
            program_uuid=program_uuid,
            site=site
        )
    except IntegrityError:
        logger.exception('Failed to create vouchers for [%s] coupon.', coupon_product.title)
        raise

    attach_vouchers_to_coupon_product(coupon_product, vouchers, note, enterprise_id=enterprise_customer,
                                      sales_force_id=sales_force_id,
                                      salesforce_opportunity_line_item=salesforce_opportunity_line_item)

    return coupon_product


def create_coupon_product_and_stockrecord(title, category, partner, price):
    product_class = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    coupon_product = Product.objects.create(title=title, product_class=product_class)
    ProductCategory.objects.get_or_create(product=coupon_product, category=category)
    sku = generate_sku(product=coupon_product, partner=partner)
    StockRecord.objects.update_or_create(
        defaults={
            'price_currency': settings.OSCAR_DEFAULT_CURRENCY,
            'price_excl_tax': price
        },
        partner=partner,
        partner_sku=sku,
        product=coupon_product
    )
    return coupon_product


def attach_or_update_contract_metadata_on_coupon(coupon, **update_kwargs):
    """
    Creates a enterprise_contract_metadata object and assigns it as an attr
    of the coupon product if it does not exist.

    If enterprise_contract_metadata attr exists, uses kwargs provided to
    update the existing object.

    Expected kwargs based on model:
    contract_discount_type, contract_discount_value, prepaid_invoice_amount
    """
    try:
        contract_metadata = coupon.attr.enterprise_contract_metadata
    except AttributeError:
        contract_metadata = EnterpriseContractMetadata()
        coupon.attr.enterprise_contract_metadata = contract_metadata

    for key, value in update_kwargs.items():
        logger.info(
            'Setting attribute [%s] to [%s] on contract_metadata for coupon [%s]',
            key, value, coupon.id
        )
        setattr(contract_metadata, key, value)

    contract_metadata.clean()
    contract_metadata.save()
    coupon.save()


def attach_vouchers_to_coupon_product(coupon_product, vouchers, note, notify_email=None, enterprise_id=None,
                                      sales_force_id=None, salesforce_opportunity_line_item=None):
    coupon_vouchers, __ = CouponVouchers.objects.get_or_create(coupon=coupon_product)
    coupon_vouchers.vouchers.add(*vouchers)
    coupon_product.attr.coupon_vouchers = coupon_vouchers
    coupon_product.attr.note = note
    if notify_email:
        coupon_product.attr.notify_email = notify_email
    if sales_force_id:
        coupon_product.attr.sales_force_id = sales_force_id
    if salesforce_opportunity_line_item:
        coupon_product.attr.salesforce_opportunity_line_item = salesforce_opportunity_line_item
    if enterprise_id:
        coupon_product.attr.enterprise_customer_uuid = enterprise_id
    coupon_product.save()


def generate_sku(product, partner):
    """
    Generates a SKU for the given partner and and product combination.

    Example: 76E4E71
    """
    if not product.get_product_class():
        raise AttributeError('Product has no product class')

    if product.is_coupon_product:
        _hash = ' '.join((
            str(product.id),
            str(partner.id)
        )).encode('utf-8')
    elif product.is_enrollment_code_product:
        _hash = ' '.join((
            getattr(product.attr, 'course_key', ''),
            getattr(product.attr, 'seat_type', ''),
            str(partner.id)
        )).encode('utf-8')
    elif product.is_seat_product:
        _hash = ' '.join((
            getattr(product.attr, 'certificate_type', ''),
            str(product.attr.course_key),
            str(product.attr.id_verification_required),
            getattr(product.attr, 'credit_provider', ''),
            str(product.id),
            str(partner.id)
        )).encode('utf-8')
    elif product.is_course_entitlement_product:
        _hash = ' '.join((
            getattr(product.attr, 'certificate_type', ''),
            str(product.attr.UUID),
            str(partner.id)
        )).encode('utf-8')

    else:
        raise Exception('Unexpected product class')

    md5_hash = md5(_hash.lower())
    digest = md5_hash.hexdigest()[-7:]

    return digest.upper()


def get_or_create_catalog(name, partner, stock_record_ids):
    """
    Returns the catalog which has the same name, partner and stock records.
    If there isn't one with that data, creates and returns a new one.
    """
    catalogs = Catalog.objects.all()
    stock_records = [StockRecord.objects.get(id=id) for id in stock_record_ids]  # pylint: disable=redefined-builtin

    for catalog in catalogs:
        if catalog.name == name and catalog.partner == partner:
            if set(catalog.stock_records.all()) == set(stock_records):
                return catalog, False

    catalog = Catalog.objects.create(name=name, partner=partner)
    for stock_record in stock_records:
        catalog.stock_records.add(stock_record)
    return catalog, True


def _get_next_character(character):
    """
    Provides next alphabetic character
    """
    ascii_code = ord(character)
    # If character is 'Z', then return 'A' and indicate that next character should also be updated
    if ascii_code + 1 > 90:
        return chr(65), True
    # If the character is '0', replace it with 'A'
    if ascii_code == 48:
        return chr(65), False
    return chr(ascii_code + 1), False


def _get_path_for_next(old_path):
    """
    Provides path for the next child
    """
    path = list(old_path)
    for i in reversed(range(len(path))):
        updated_character, to_update_next = _get_next_character(old_path[i])
        path[i] = updated_character
        # Check whether next character should be updated or not
        if not to_update_next:
            break
    return "".join(path)


def create_subcategories(model, parent_category_name, categories):
    """
    Create children for parent category. An alternative from create_from_breadcrumbs method of django-oscar
    as that method can't be used in data migrations. This model requests the model class as a parameter
    so we can provide an historical version.
    """
    if model.__name__ != 'Category':
        return
    Category = model
    parent_category = Category.objects.get(name=parent_category_name)
    last_path = Category.objects.filter(path__contains=parent_category.path).order_by('-path')[0].path
    # 4 digits path means this category has no children yet so set initial path
    if len(last_path) == 4:
        last_path = f"{last_path}0000"
    actual_created_count = 0
    for category in categories:
        new_path = _get_path_for_next(last_path)
        _, created = Category.objects.get_or_create(
            name=category,
            depth=2,
            path=new_path
        )
        last_path = new_path
        if created:
            actual_created_count += 1

    parent_category.numchild = parent_category.numchild + actual_created_count
    parent_category.save()
