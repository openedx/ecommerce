import mock

from ecommerce.extensions.payment.models import PaymentProcessorResponse
from ecommerce.extensions.payment.processors.paypal import Paypal
from ecommerce.extensions.test.factories import create_basket
from ecommerce.management.utils import refund_basket_transactions
from ecommerce.tests.testcases import TestCase


class RefundBasketTransactionsTests(TestCase):
    def test_no_basket_ids(self):
        assert refund_basket_transactions(self.site, []) == (0, 0,)

    def test_success(self):
        basket = create_basket(site=self.site)
        ppr = PaymentProcessorResponse.objects.create(basket=basket, transaction_id='abc', processor_name='paypal')
        with mock.patch.object(Paypal, 'issue_credit') as mock_issue_credit:
            mock_issue_credit.return_value = None

            assert refund_basket_transactions(self.site, [basket.id]) == (1, 0,)
            mock_issue_credit.assert_called_once_with(
                basket.order_number, basket, ppr.transaction_id, basket.total_excl_tax, basket.currency
            )

    def test_failure(self):
        basket = create_basket(site=self.site)
        PaymentProcessorResponse.objects.create(basket=basket)
        assert refund_basket_transactions(self.site, [basket.id]) == (0, 1,)
