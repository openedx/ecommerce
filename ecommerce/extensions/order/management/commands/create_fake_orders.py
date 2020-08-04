

import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from oscar.core.loading import get_class, get_model

from ecommerce.tests.factories import UserFactory

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
Basket = get_model('basket', 'Basket')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')
Default = get_class('partner.strategy', 'Default')
Free = get_class('shipping.methods', 'Free')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderCreator = get_class('order.utils', 'OrderCreator')


def create_basket(owner, product, site):
    """Create basket to place order"""
    basket = Basket.objects.create(site=site, owner=owner)
    basket.strategy = Default()
    basket.add_product(product)
    basket.save()
    return basket


class Command(BaseCommand):
    help = 'Added Fake orders for testing'

    def add_arguments(self, parser):
        parser.add_argument('--count',
                            action='store',
                            dest='orders',
                            type=int,
                            required=True,
                            help='Number of orders to create.')
        parser.add_argument('--sku',
                            action='store',
                            dest='sku',
                            type=str,
                            required=True,
                            help='SKU corresponding to the product for which orders will be created.')

    def handle(self, *args, **options):
        orders = options['orders']
        sku = options['sku']

        try:
            stock_record = StockRecord.objects.get(partner_sku=sku)
            product = stock_record.product
            partner = stock_record.partner
        except StockRecord.DoesNotExist:
            msg = 'No StockRecord for partner_sku {} exists.'.format(sku)
            logger.exception(msg)
            raise CommandError(msg)

        site = partner.default_site
        if not site:
            msg = 'No default site exists for partner {}!'.format(partner.id)
            logger.exception(msg)
            raise CommandError(msg)

        user = UserFactory()

        for __ in range(orders):
            basket = create_basket(user, product, site)

            shipping_method = Free()
            shipping_charge = shipping_method.calculate(basket)
            total = OrderTotalCalculator().calculate(basket, shipping_charge)
            number = OrderNumberGenerator().order_number(basket)
            with transaction.atomic():
                OrderCreator().place_order(
                    order_number=number,
                    user=user,
                    basket=basket,
                    shipping_address=None,
                    shipping_method=shipping_method,
                    shipping_charge=shipping_charge,
                    billing_address=None,
                    total=total)

                basket.set_as_submitted()
