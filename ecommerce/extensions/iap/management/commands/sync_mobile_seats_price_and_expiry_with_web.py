"""
This command sync mobile seat price and expiry with web seat price and expiry.
"""
import logging

from django.core.management import BaseCommand

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.courses.constants import CertificateType
from ecommerce.extensions.catalogue.models import Product

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Sync expiry and price of mobile seats with respective web seat.
    """

    help = 'Sync expiry and price of mobile seats with respective web seat.'

    def handle(self, *args, **options):
        mobile_enabled_products = Product.objects.filter(
            structure=Product.PARENT,
            product_class__name=SEAT_PRODUCT_CLASS_NAME,
            children__attribute_values__attribute__name="certificate_type",
            children__attribute_values__value_text=CertificateType.VERIFIED,
            children__stockrecords__isnull=False,
            children__stockrecords__partner_sku__icontains="mobile",
        ).distinct()

        for product in mobile_enabled_products:
            mobile_seats = Product.objects.filter(
                parent=product,
                attribute_values__attribute__name="certificate_type",
                attribute_values__value_text=CertificateType.VERIFIED,
                stockrecords__partner_sku__icontains="mobile",
            )

            web_seat = Product.objects.filter(
                parent=product,
                attribute_values__attribute__name="certificate_type",
                attribute_values__value_text=CertificateType.VERIFIED,
            ).exclude(stockrecords__partner_sku__icontains="mobile").first()

            if not web_seat:
                logger.info('While syncing could not find web seat for {}'.format(product.title) )
                continue

            for mobile_seat in mobile_seats:
                info = 'Syncing {} with {}'.format(mobile_seat.title, web_seat.title)
                logger.info(info)

                stock_record = mobile_seat.stockrecords.all()[0]
                stock_record.price_excl_tax = web_seat.stockrecords.all()[0].price_excl_tax
                mobile_seat.expires = web_seat.expires
                stock_record.save()
                mobile_seat.save()
