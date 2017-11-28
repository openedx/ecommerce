import mock
from django.db import transaction
from django.test import override_settings
from oscar.core.loading import get_class, get_model
from oscar.test.factories import ProductFactory, RangeFactory

from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.constants import CARD_TYPES
from ecommerce.extensions.payment.models import PaymentProcessorResponse
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.processors.paypal import Paypal
from ecommerce.extensions.test.factories import UserFactory, create_basket, prepare_voucher
from ecommerce.management.utils import FulfillFrozenBaskets, refund_basket_transactions
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
    def test_success_with_cybersource(self):
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
            'req_card_type': CARD_TYPES['visa']['cybersource_code']
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
        basket = create_basket(site=self.site)
        basket.status = 'Frozen'
        basket.save()

        PaymentProcessorResponse.objects.create(basket=basket, transaction_id='PAY-123', processor_name='paypal')
        assert FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)

        order = Order.objects.get(number=basket.order_number)
        assert order.status == 'Complete'

        total = basket.total_incl_tax_excl_discounts
        Source.objects.get(
            source_type__name=Paypal.NAME, currency=order.currency, amount_allocated=total, amount_debited=total,
            label='PayPal Account', card_type=None)
        PaymentEvent.objects.get(event_type__name=PaymentEventTypeName.PAID, amount=total,
                                 processor_name=Paypal.NAME)

    def test_multiple_transactions(self):
        basket = create_basket(site=self.site)
        basket.status = 'Frozen'
        basket.save()
        PaymentProcessorResponse.objects.create(basket=basket, transaction_id='abc', processor_name='cybersource')
        PaymentProcessorResponse.objects.create(basket=basket, transaction_id='PAY-123', processor_name='paypal')

        assert not FulfillFrozenBaskets().fulfill_basket(basket.id, self.site)

    def test_invalid_basket(self):
        assert not FulfillFrozenBaskets().fulfill_basket(100, self.site)

    def test_order_exist_exception(self):
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
