import logging

from django.core.management import BaseCommand

from ecommerce.extensions.catalogue.models import Product
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Squash duplicate invoices for coupon orders.
    When we moved from re-using a coupon some of them had already more than one invoice,
    and we are not having that! Monogamy rulez here, yerr damn hippies!
    """
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    def handle(self, *args, **options):
        for coupon in Product.objects.filter(product_class__name='Coupon'):
            qs = Invoice.objects.filter(order__basket__lines__product=coupon).order_by('created')
            if qs.count() > 1:
                qs.exclude(pk=qs.first().id).delete()
                logger.info('Deleted douplicate invoices of coupon %s', coupon.id)
