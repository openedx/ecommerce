

import mock
from django.db import transaction
from django.test import override_settings
from oscar.core.loading import get_class, get_model
from oscar.test.factories import ProductFactory, RangeFactory, create_order

from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.constants import CARD_TYPES
from ecommerce.extensions.payment.models import PaymentProcessorResponse
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.processors.paypal import Paypal
from ecommerce.extensions.test.factories import create_basket, prepare_voucher
from ecommerce.management.utils import FulfillFrozenBaskets, refund_basket_transactions
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

Free = get_class('shipping.methods', 'Free')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
OrderCreator = get_class('order.utils', 'OrderCreator')

Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
Source = get_model('payment', 'Source')


class RefundBasketTransactionsTests(TestCase):
    def test_no_basket_ids(self):
        assert refund_basket_transactions(self.site, []) == (0, 0,)

    def test_success(self):
        product_price = 100
        percentage_discount = 10
        product = ProductFactory(stockrecords__price_excl_tax=product_price)
        voucher, product = prepare_voucher(_range=RangeFactory(products=[product]), benefit_value=percentage_discount)
        self.request.user = UserFactory()
        basket = prepare_basket(self.request, [product], voucher)

        ppr = PaymentProcessorResponse.objects.create(basket=basket, transaction_id='abc', processor_name='paypal')
        with mock.patch.object(Paypal, 'issue_credit') as mock_issue_credit:
            mock_issue_credit.return_value = None

            assert refund_basket_transactions(self.site, [basket.id]) == (1, 0,)
            total = product_price * (100 - percentage_discount) / 100.
            mock_issue_credit.assert_called_once_with(
                basket.order_number, basket, ppr.transaction_id, total, basket.currency
            )

    def test_failure(self):
        basket = create_basket(site=self.site)
        PaymentProcessorResponse.objects.create(basket=basket)
        assert refund_basket_transactions(self.site, [basket.id]) == (0, 1,)


@override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule', ])
class FulfillFrozenBasketsTests(TestCase):
    """ Test Fulfill Frozen Basket class"""

    def _dummy_basket_data(self):
        """ Creates dummy basket data for testing."""
        basket = create_basket(site=self.site)
        basket.status = 'Frozen'
        basket.save()
        PaymentProcessorResponse.objects.create(basket=basket, transaction_id='PAY-123', processor_name='paypal',
                                                response={'state': 'approved'})
        return basket

    @staticmethod
    def _dummy_order_data(status=ORDER.COMPLETE):
        """ Creates dummy order data for testing."""
        order = create_order()
        order.status = status
        order.save()
        order.basket.freeze()
        return order.basket

    def test_success_with_cybersource(self):
        """ Test basket with cybersource payment basket."""
        product_price = 100
        percentage_discount = 10
        product = ProductFactory(stockrecords__price_excl_tax=product_price)
        voucher, product = prepare_voucher(_range=RangeFactory(products=[product]), benefit_value=percentage_discount)
        self.request.user = UserFactory()
        basket = prepare_basket(self.request, [product], voucher)
        basket.status = 'Frozen'
        basket.save()

        card_number = '4111111111111111'
        response = {
            'req_card_number': card_number,
            'req_card_type': CARD_TYPES['visa']['cybersource_code'],
            u'decision': u'ACCEPT',
        }
        PaymentProcessorResponse.objects.create(basket=basket, transaction_id='abc', processor_name='cybersource',
                                                response=response)
        assert FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)

        order = Order.objects.get(number=basket.order_number)
        assert order.status == 'Complete'

        total = product_price * (100 - percentage_discount) / 100.
        Source.objects.get(
            source_type__name=Cybersource.NAME, currency=order.currency, amount_allocated=total, amount_debited=total,
            label=card_number, card_type='visa')
        PaymentEvent.objects.get(event_type__name=PaymentEventTypeName.PAID, amount=total,
                                 processor_name=Cybersource.NAME)

    def test_success_with_paypal(self):
        """ Test basket with paypal payment basket."""
        basket = self._dummy_basket_data()

        assert FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)

        order = Order.objects.get(number=basket.order_number)
        assert order.status == 'Complete'

        total = basket.total_incl_tax_excl_discounts
        Source.objects.get(
            source_type__name=Paypal.NAME, currency=order.currency, amount_allocated=total, amount_debited=total,
            label='Paypal Account', card_type=None)
        PaymentEvent.objects.get(event_type__name=PaymentEventTypeName.PAID, amount=total,
                                 processor_name=Paypal.NAME)

    def test_multiple_transactions(self):
        """ Test utility against multiple payment processor responses."""
        basket = self._dummy_basket_data()
        PaymentProcessorResponse.objects.create(basket=basket, transaction_id='abc', processor_name='cybersource',
                                                response={u'decision': u'ACCEPT'})
        assert FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)

    def test_no_successful_transaction(self):
        """ Test utility when basket have no successful payment processor response."""
        basket = create_basket(site=self.site)
        basket.status = 'Frozen'
        basket.save()

        assert not FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)

    def test_invalid_basket(self):
        """ Test utility for invalid basket id."""
        assert not FulfillFrozenBaskets().fulfill_basket(100, self.site)

    def test_order_exist_exception(self):
        """ Test utility for case where order already exists."""
        basket = create_basket(site=self.site)
        basket.status = 'Frozen'
        basket.save()
        card_number = '4111111111111111'
        response = {
            'req_card_number': card_number,
            'req_card_type': CARD_TYPES['visa']['cybersource_code']
        }
        PaymentProcessorResponse.objects.create(basket=basket, transaction_id='abc', processor_name='cybersource',
                                                response=response)

        shipping_method = Free()
        shipping_charge = shipping_method.calculate(basket)
        total = OrderTotalCalculator().calculate(basket, shipping_charge)
        number = OrderNumberGenerator().order_number(basket)
        with transaction.atomic():
            OrderCreator().place_order(
                order_number=number,
                user=basket.owner,
                basket=basket,
                shipping_address=None,
                shipping_method=shipping_method,
                shipping_charge=shipping_charge,
                billing_address=None,
                total=total)

            basket.set_as_submitted()

        assert not FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)

    def test_complete_order_basket(self):
        """ Test when basket have a fulfilled order."""
        basket = self._dummy_order_data(status=ORDER.COMPLETE)
        assert FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)

    def test_fulfillment_error_order_basket(self):
        """ Test fulfillment error order basket is fulfilled when called for basket."""
        basket = self._dummy_order_data(status=ORDER.FULFILLMENT_ERROR)

        assert FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)
        order = Order.objects.get(basket=basket)
        self.assertEqual(order.status, ORDER.COMPLETE)

    def test_when_unable_to_fulfill_order(self):
        """ Test returns false when unable to complete fulfillment of order. """
        basket = self._dummy_order_data(status=ORDER.FULFILLMENT_ERROR)

        with mock.patch('ecommerce.extensions.order.processing.EventHandler.handle_shipping_event',
                        return_value='pumpkins'):
            assert not FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)
        order = Order.objects.get(basket=basket)
        self.assertEqual(order.is_fulfillable, True)

    def test_when_unable_to_fulfill_basket(self):
        """ Test returns false when unable to fulfill basket."""
        basket = self._dummy_basket_data()

        with mock.patch('ecommerce.extensions.checkout.mixins.EdxOrderPlacementMixin.handle_order_placement',
                        side_effect=Exception):
            assert not FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)

    def test_with_expired_voucher(self):
        """ Test creates order when called with basket with expired voucher"""
        basket = create_basket()
        product = ProductFactory(stockrecords__price_excl_tax=100, stockrecords__partner=self.partner,
                                 stockrecords__price_currency='USD')
        voucher, product = prepare_voucher(code='TEST101', _range=RangeFactory(products=[product]))
        self.request.user = UserFactory()
        basket.add_product(product)
        basket.vouchers.add(voucher)
        basket.status = 'Frozen'
        basket.save()

        PaymentProcessorResponse.objects.create(basket=basket, transaction_id='PAY-123', processor_name='paypal',
                                                response={'state': 'approved'})
        with mock.patch('oscar.apps.offer.applicator.Applicator.apply', side_effect=ValueError):
            assert FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)
