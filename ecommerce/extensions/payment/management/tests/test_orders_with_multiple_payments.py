import datetime
import ddt
from factory.django import mute_signals
from django.core.urlresolvers import reverse
from django.core.management import call_command
from django.core.management.base import CommandError

from oscar.test import factories
from oscar.core.loading import get_class, get_model
from oscar.test.contextmanagers import mock_signal_receiver
from ecommerce.core.tests.patched_httpretty import httpretty

from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.processors.paypal import Paypal
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin, CybersourceMixin, PaypalMixin
from ecommerce.extensions.payment.management.commands.orders_with_multiple_payments import Command
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
SourceType = get_model('payment', 'SourceType')

post_checkout = get_class('checkout.signals', 'post_checkout')


@ddt.ddt
class TestOrdersWithMultiplePaymentsCommand(PaypalMixin, CybersourceMixin, PaymentEventsMixin, TestCase):
    """ Tests processing of orders_with_multiple_payments command for cybersouce and paypal orders"""

    def setUp(self):
        super(TestOrdersWithMultiplePaymentsCommand, self).setUp()
        self.user = factories.UserFactory()
        self.billing_address = self.make_billing_address()

        self.basket = factories.create_basket()
        self.basket.owner = self.user
        self.basket.freeze()

        self.cybersource_processor = Cybersource()
        self.cybersource_processor_name = self.cybersource_processor.NAME

        self.paypal_processor = Paypal()
        self.paypal_processor_name = self.paypal_processor.NAME

    def test_command_handler_without_args(self):
        """
        Tests the processing of main command handler with out the arguments.
        """
        with self.assertRaises(CommandError) as exception:
            call_command('orders_with_multiple_payments')
            self.assertEqual(exception.message, "Required arguments `Start Date` and `End Date` are missing.")

    @ddt.unpack
    @ddt.data(
        ('01-02-2016', '01-01-2016', "Argument `Start Date` must be less than `End Date`."),
        ('2016-02-01', '01-01-2016', "Start Date was not specified or specified correctly in args 'd-m-y'.")
    )
    def test_command_handler_with_args(self, start_date, end_date, message):
        """
        Tests the processing of main command handler with the arguments.
        """
        with self.assertRaises(CommandError) as exception:
            call_command('orders_with_multiple_payments', start_date, end_date)
            self.assertEqual(exception.message, message)

    @mute_signals(post_checkout)
    def test_number_of_payments_for_cybersource(self):
        """
        Tests the processing of 'number_of_payments_for_order' method for cybersource orders.
        """
        # Generate payment response for cybersource
        notification = self.generate_notification(
            self.cybersource_processor.secret_key,
            self.basket,
            billing_address=self.billing_address,
        )
        with mock_signal_receiver(post_checkout):
            response = self.client.post(reverse('cybersource_notify'), notification)
        # Check Mock call was successful and order was created.
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get(basket=self.basket)
        self.assertIsNotNone(order)
        self.assertEqual(order.status, ORDER.OPEN)
        # Test method returns no of payments equals to 1
        self.assertEquals(Command.number_of_payments_for_order(order), 1)
        # Duplicate Response
        response = PaymentProcessorResponse.objects.get(basket_id=order.basket_id)
        response.id += 1
        response.save()
        # Test method returns no of payments equal to 2
        self.assertEquals(Command.number_of_payments_for_order(order), 2)
        order.date_placed = datetime.datetime.strptime('01-02-2016', '%d-%m-%Y')
        order.save()
        call_command('orders_with_multiple_payments', '01-01-2016', '01-02-2016')
        # Change one Response to refund from payment
        response.response[u'reconciliationID'] = u'32764148197'
        del response.response[u'req_transaction_type']
        response.save()
        # One payment one refund total no of not refunded payments = 0
        self.assertEquals(Command.number_of_payments_for_order(order), 0)

    @httpretty.activate
    def test_number_of_payments_for_paypal(self):
        """
        Tests the processing of 'number_of_payments_for_order' method for Paypal orders.
        """
        # Genrate Payment Responses for Paypal
        self.mock_oauth2_response()
        self.mock_payment_creation_response(self.basket)
        self.paypal_processor.get_transaction_parameters(self.basket, request=self.request)
        self.mock_payment_creation_response(self.basket, find=True)
        self.mock_payment_execution_response(self.basket)
        self.client.get(reverse('paypal_execute'), self.RETURN_DATA)
        # Check order has been created after the payment
        order = Order.objects.get(basket_id=self.basket.id)
        self.assertIsNotNone(order)
        # Remove 'update_time' as it's never a part of real first paypal response.
        payment_response = PaymentProcessorResponse.objects.first()
        del payment_response.response[u'update_time']
        payment_response.save()
        # Test method returns 0 if payment has been refunded
        self.assertEquals(Command.number_of_payments_for_order(order), 0)
        # Remove 'Refund' fields from the second response.
        payment_response = PaymentProcessorResponse.objects.all()[1]
        del payment_response.response[u'transactions'][0][u'related_resources'][0][u'sale'][u'links'][1]
        payment_response.save()
        # Test method returns no of payments equals to 1
        self.assertEquals(Command.number_of_payments_for_order(order), 1)
        # Change one Response to refund from payment
        payment_response = PaymentProcessorResponse.objects.first()
        payment_response.id = 3
        payment_response.save()
        self.assertEquals(Command.number_of_payments_for_order(order), 2)
        order.date_placed = datetime.datetime.strptime('01-02-2016', '%d-%m-%Y')
        order.save()
        call_command('orders_with_multiple_payments', '01-01-2016', '01-02-2016')
