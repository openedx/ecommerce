import logging

from django.db.models import Q
from oscar.core.loading import get_class

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.courses.constants import CertificateType
from ecommerce.extensions.catalogue.models import Product
from ecommerce.extensions.iap.constants import ANDROID_SKU_PREFIX, IOS_SKU_PREFIX, MISSING_WEB_SEAT_ERROR
from ecommerce.extensions.partner.models import StockRecord

Dispatcher = get_class('communication.utils', 'Dispatcher')
logger = logging.getLogger(__name__)


def create_child_products_for_mobile(product):
    """
    Create child products/seats for IOS and Android.
    Child product is also called a variant in the UI
    """
    existing_web_seat = Product.objects.filter(
        ~Q(stockrecords__partner_sku__icontains="mobile"),
        parent=product,
        attribute_values__attribute__name="certificate_type",
        attribute_values__value_text=CertificateType.VERIFIED,
        parent__product_class__name=SEAT_PRODUCT_CLASS_NAME,
    ).first()
    if existing_web_seat:
        android_seat = create_mobile_seat(ANDROID_SKU_PREFIX, existing_web_seat)
        ios_seat = create_mobile_seat(IOS_SKU_PREFIX, existing_web_seat)
        return android_seat, ios_seat

    logger.error(MISSING_WEB_SEAT_ERROR, product.course.id)
    return None


def create_mobile_seat(sku_prefix, existing_web_seat):
    """
    Create a mobile seat, attributes and stock records matching the given existing_web_seat
    in the same Parent Product.
    """
    new_mobile_seat, _ = Product.objects.get_or_create(
        title="{} {}".format(sku_prefix.capitalize(), existing_web_seat.title.lower()),
        course=existing_web_seat.course,
        parent=existing_web_seat.parent,
        product_class=existing_web_seat.product_class,
        structure=existing_web_seat.structure
    )
    new_mobile_seat.expires = existing_web_seat.expires
    new_mobile_seat.is_public = existing_web_seat.is_public
    new_mobile_seat.save()

    # Set seat attributes
    new_mobile_seat.attr.certificate_type = existing_web_seat.attr.certificate_type
    new_mobile_seat.attr.course_key = existing_web_seat.attr.course_key
    new_mobile_seat.attr.id_verification_required = existing_web_seat.attr.id_verification_required
    if 'ios' in sku_prefix:
        # We need this attribute defined for ios products
        # Actual values will be assigned when we create product on appstore
        app_store_id = getattr(new_mobile_seat.attr, 'app_store_id', None)
        if not app_store_id:
            new_mobile_seat.attr.app_store_id = ''

    new_mobile_seat.attr.save()

    # Create stock records
    existing_stock_record = existing_web_seat.stockrecords.first()
    mobile_stock_record, created = StockRecord.objects.get_or_create(
        product=new_mobile_seat,
        partner=existing_stock_record.partner
    )
    if created:
        partner_sku = 'mobile.{}.{}'.format(sku_prefix.lower(), existing_stock_record.partner_sku.lower())
        mobile_stock_record.partner_sku = partner_sku
    mobile_stock_record.price_currency = existing_stock_record.price_currency
    mobile_stock_record.price = existing_stock_record.price
    mobile_stock_record.save()

    return mobile_stock_record
