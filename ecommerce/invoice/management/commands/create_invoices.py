""" This command invoices for orders that don't have them. """
import logging

from django.core.management import BaseCommand

from ecommerce.core.models import BusinessClient
from ecommerce.extensions.basket.models import Basket
from ecommerce.extensions.catalogue.models import Product
from ecommerce.extensions.order.models import Order
from ecommerce.extensions.payment.processors.invoice import InvoicePayment
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Create invoices for orders that don't have them.
    At some point in the past we decided to use the BusinessClient from invoices,
    before that it was used from basket objects, and the orders back then didn't have
    invoices. This command creates invoices for those orders.
    """

    def handle(self, *args, **options):
        for coupon in Product.objects.filter(product_class__name='Coupon'):
            try:
                basket = Basket.objects.filter(lines__product=coupon, status=Basket.SUBMITTED).first()
                if basket is None:
                    raise Basket.DoesNotExist
                order = Order.objects.get(basket=basket)
                Invoice.objects.get(order=order)
                logger.info('Invoice for order %s already exists - skipping.', order.number)
            except Basket.DoesNotExist:
                logger.error('Basket for coupon %s does not exist!', coupon.id)
            except Order.DoesNotExist:
                logger.error('Order for basket %s does not exist!', basket.id)
            except Invoice.DoesNotExist:
                client, __ = BusinessClient.objects.get_or_create(name=basket.owner.username)
                InvoicePayment().handle_processor_response(response={}, order=order, business_client=client)
                logger.info('Created new invoice for order %s.', order.number)
