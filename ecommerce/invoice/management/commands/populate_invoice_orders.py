import logging

from django.core.management import BaseCommand
from oscar.core.loading import get_model

from ecommerce.core.models import BusinessClient
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')


class Command(BaseCommand):
    """
    Populate the order field for all invoices from the basket order,
    and set the basket values to None. Creates a new business client object
    from the basket owner username value and assigns it to the invoice if there
    is not one assigned already.
    """
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    def handle(self, *args, **options):
        for invoice in Invoice.objects.all():
            if invoice.basket:
                try:
                    order = Order.objects.get(basket=invoice.basket)
                    invoice.order = order
                    if not invoice.business_client:
                        invoice.business_client, __ = BusinessClient.objects.get_or_create(
                            name=invoice.basket.owner.username
                        )
                    invoice.basket = None
                    invoice.save()
                    logger.info('Order [%d] saved to invoice [%d].', order.id, invoice.id)
                except Order.DoesNotExist:
                    logger.info('Order for basket [%s] does not exist.', invoice.basket)
