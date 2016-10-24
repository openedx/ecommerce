""" Tests of the Payment Views. """
from __future__ import unicode_literals

import json

import ddt
import mock
from django.conf import settings
from django.core.urlresolvers import reverse
from factory.django import mute_signals
from freezegun import freeze_time
from oscar.apps.order.exceptions import UnableToPlaceOrder
from oscar.apps.payment.exceptions import PaymentError, UserCancelled, TransactionDeclined
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from oscar.test.contextmanagers import mock_signal_receiver
from testfixtures import LogCapture

from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin, CybersourceMixin
from ecommerce.extensions.payment.views.cybersource import CybersourceNotifyView
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Selector = get_class('partner.strategy', 'Selector')
SourceType = get_model('payment', 'SourceType')

post_checkout = get_class('checkout.signals', 'post_checkout')


@ddt.ddt
class CybersourceNotifyViewTests(CybersourceMixin, PaymentEventsMixin, TestCase):
    """ Test processing of CyberSource notifications. """

    def setUp(self):
        super(CybersourceNotifyViewTests, self).setUp()

        self.toggle_ecommerce_receipt_page(True)

        self.user = factories.UserFactory()
        self.billing_address = self.make_billing_address()

        self.basket = factories.create_basket()
        self.basket.owner = self.user
        self.basket.freeze()

        self.processor = Cybersource(self.site)
        self.processor_name = self.processor.NAME

    def _assert_payment_data_recorded(self, notification):
        """ Ensure PaymentEvent, PaymentProcessorResponse, and Source objects are created for the basket. """

        # Ensure the response is stored in the database
        self.assert_processor_response_recorded(self.processor_name, notification['transaction_id'], notification,
                                                basket=self.basket)

        # Validate a payment Source was created
        reference = notification['transaction_id']
        source_type = SourceType.objects.get(code=self.processor_name)
        label = notification['req_card_number']
        self.assert_payment_source_exists(self.basket, source_type, reference, label)

        # Validate that PaymentEvents exist
        paid_type = PaymentEventType.objects.get(code='paid')
        self.assert_payment_event_exists(self.basket, paid_type, reference, self.processor_name)

    def _assert_processing_failure(self, notification, status_code, error_message, log_level='ERROR'):
        """Verify that payment processing operations fail gracefully."""
        logger_name = 'ecommerce.extensions.payment.views.cybersource'
        with LogCapture(logger_name) as l:
            response = self.client.post(reverse('cybersource_notify'), notification)

            self.assertEqual(response.status_code, status_code)

            self.assert_processor_response_recorded(
                self.processor_name,
                notification[u'transaction_id'],
                notification,
                basket=self.basket
            )

            l.check(
                (
                    logger_name,
                    'INFO',
                    'Received CyberSource merchant notification for transaction [{transaction_id}], '
                    'associated with basket [{basket_id}].'.format(
                        transaction_id=notification[u'transaction_id'],
                        basket_id=self.basket.id
                    )
                ),
                (logger_name, log_level, error_message)
            )

    # Disable the normal signal receivers so that we can verify the state of the created order.
    @mute_signals(post_checkout)
    def test_accepted(self):
        """
        When payment is accepted, the following should occur:
            1. The response is recorded and PaymentEvent/Source objects created.
            2. An order for the corresponding basket is created.
            3. The order is fulfilled.
        """

        # The basket should not have an associated order if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        notification = self.generate_notification(self.basket, billing_address=self.billing_address)

        with mock_signal_receiver(post_checkout) as receiver:
            response = self.client.post(reverse('cybersource_notify'), notification)

            # Validate that a new order exists in the correct state
            order = Order.objects.get(basket=self.basket)
            self.assertIsNotNone(order, 'No order was created for the basket after payment.')
            self.assertEqual(order.status, ORDER.OPEN)

            # Validate the order's line items
            self.assertListEqual(list(order.lines.values_list('product__id', flat=True)),
                                 list(self.basket.lines.values_list('product__id', flat=True)))

            # Verify the post_checkout signal was emitted
            self.assertEqual(receiver.call_count, 1)
            __, kwargs = receiver.call_args
            self.assertEqual(kwargs['order'], order)

        # The view should always return 200
        self.assertEqual(response.status_code, 200)

        # Validate the payment data was recorded for auditing
        self._assert_payment_data_recorded(notification)

        # The basket should be marked as submitted. Refresh with data from the database.
        basket = Basket.objects.get(id=self.basket.id)
        self.assertTrue(basket.is_submitted)
        self.assertIsNotNone(basket.date_submitted)

    @ddt.data('CANCEL', 'DECLINE', 'ERROR', 'blah!')
    def test_not_accepted(self, decision):
        """
        When payment is NOT accepted, the processor's response should be saved to the database. An order should NOT
        be created.
        """

        notification = self.generate_notification(self.basket, decision=decision)
        response = self.client.post(reverse('cybersource_notify'), notification)

        # The view should always return 200
        self.assertEqual(response.status_code, 200)

        # The basket should not have an associated order if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        # Ensure the response is stored in the database
        self.assert_processor_response_recorded(self.processor_name, notification[u'transaction_id'], notification,
                                                basket=self.basket)

    @ddt.data(
        (PaymentError, 200, 'ERROR', 'CyberSource payment failed for basket [{basket_id}]. '
                                     'The payment response was recorded in entry [{response_id}].'),
        (UserCancelled, 200, 'INFO', 'CyberSource payment did not complete for basket [{basket_id}] because '
                                     '[UserCancelled]. The payment response was recorded in entry [{response_id}].'),
        (TransactionDeclined, 200, 'INFO', 'CyberSource payment did not complete for basket [{basket_id}] because '
                                           '[TransactionDeclined]. The payment response was recorded in entry '
                                           '[{response_id}].'),
        (KeyError, 500, 'ERROR', 'Attempts to handle payment for basket [{basket_id}] failed.')
    )
    @ddt.unpack
    def test_payment_handling_error(self, error_class, status_code, log_level, error_message):
        """
        Verify that CyberSource's merchant notification is saved to the database despite an error handling payment.
        """
        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        with mock.patch.object(CybersourceNotifyView, 'handle_payment', side_effect=error_class) as fake_handle_payment:
            self._assert_processing_failure(
                notification,
                status_code,
                error_message.format(basket_id=self.basket.id, response_id=1),
                log_level
            )
            self.assertTrue(fake_handle_payment.called)

    def test_unable_to_place_order(self):
        """ When payment is accepted, but an order cannot be placed, log an error and return HTTP 200. """

        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )

        # Verify that anticipated errors are handled gracefully.
        with mock.patch.object(CybersourceNotifyView, 'handle_order_placement',
                               side_effect=UnableToPlaceOrder) as fake_handle_order_placement:
            error_message = 'Payment was received, but an order for basket [{basket_id}] could not be placed.'.format(
                basket_id=self.basket.id,
            )
            self._assert_processing_failure(notification, 500, error_message)
            self.assertTrue(fake_handle_order_placement.called)

        # Verify that unanticipated errors are also handled gracefully.
        with mock.patch.object(CybersourceNotifyView, 'handle_order_placement',
                               side_effect=KeyError) as fake_handle_order_placement:
            error_message = 'Payment was received, but an order for basket [{basket_id}] could not be placed.'.format(
                basket_id=self.basket.id,
            )
            self._assert_processing_failure(notification, 500, error_message)
            self.assertTrue(fake_handle_order_placement.called)

    def test_invalid_basket(self):
        """ When payment is accepted for a non-existent basket, log an error and record the response. """
        order_number = '{}-{}'.format(self.partner.short_code.upper(), 101986)

        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
            req_reference_number=order_number,
        )
        response = self.client.post(reverse('cybersource_notify'), notification)

        self.assertEqual(response.status_code, 400)
        self.assert_processor_response_recorded(self.processor_name, notification[u'transaction_id'], notification)

    @ddt.data(('line2', 'foo'), ('state', 'bar'))
    @ddt.unpack
    @mock.patch('ecommerce.extensions.payment.views.cybersource.CybersourceNotifyView.handle_order_placement')
    def test_optional_fields(self, field_name, field_value, mock_placement_handler):
        """ Ensure notifications are handled properly with or without keys/values present for optional fields. """

        def check_notification_address(notification, expected_address):
            response = self.client.post(reverse('cybersource_notify'), notification)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(mock_placement_handler.called)
            actual_address = mock_placement_handler.call_args[0][6]
            self.assertEqual(actual_address.summary, expected_address.summary)

        cybersource_key = 'req_bill_to_address_{}'.format(field_name)

        # Generate a notification without the optional field set.
        # Ensure that the Cybersource key does not exist in the notification,
        # and that the address our endpoint parses from the notification is
        # equivalent to the original.
        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        self.assertNotIn(cybersource_key, notification)
        check_notification_address(notification, self.billing_address)

        # Add the optional field to the billing address in the notification.
        # Ensure that the Cybersource key now does exist, and that our endpoint
        # recognizes and parses it correctly.
        billing_address = self.make_billing_address({field_name: field_value})
        notification = self.generate_notification(
            self.basket,
            billing_address=billing_address,
        )
        self.assertIn(cybersource_key, notification)
        check_notification_address(notification, billing_address)

    def test_invalid_signature(self):
        """
        If the response signature is invalid, the view should return a 400. The response should be recorded, but an
        order should NOT be created.
        """
        notification = self.generate_notification(self.basket)
        notification[u'signature'] = u'Tampered'
        response = self.client.post(reverse('cybersource_notify'), notification)

        # The view should always return 200
        self.assertEqual(response.status_code, 400)

        # The basket should not have an associated order
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        # The response should be saved.
        self.assert_processor_response_recorded(self.processor_name, notification[u'transaction_id'], notification,
                                                basket=self.basket)


@ddt.ddt
class CybersourceSubmitViewTests(CybersourceMixin, TestCase):
    path = reverse('cybersource_submit')

    def setUp(self):
        super(CybersourceSubmitViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def _generate_data(self, basket_id):
        return {
            'basket': basket_id,
            'first_name': 'Test',
            'last_name': 'User',
            'address_line1': '141 Portland Ave.',
            'address_line2': 'Floor 9',
            'city': 'Cambridge',
            'state': 'MA',
            'postal_code': '02139',
            'country': 'US',
        }

    def _create_valid_basket(self):
        """ Creates a Basket ready for checkout. """
        basket = factories.create_basket()
        basket.owner = self.user
        basket.strategy = Selector().strategy()
        basket.site = self.site
        basket.thaw()
        return basket

    def assert_basket_retrieval_error(self, basket_id):
        error_msg = 'There was a problem retrieving your basket. Refresh the page to try again.'
        return self._assert_basket_error(basket_id, error_msg)

    def test_login_required(self):
        """ Verify the view redirects anonymous users to the login page. """
        self.client.logout()
        response = self.client.post(self.path)
        expected_url = '{base}?next={path}'.format(base=self.get_full_url(path=reverse(settings.LOGIN_URL)),
                                                   path=self.path)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @ddt.data('get', 'put', 'patch', 'head')
    def test_invalid_methods(self, method):
        """ Verify the view only supports the POST and OPTION HTTP methods."""
        response = getattr(self.client, method)(self.path)
        self.assertEqual(response.status_code, 405)

    def _assert_basket_error(self, basket_id, error_msg):
        response = self.client.post(self.path, self._generate_data(basket_id))
        self.assertEqual(response.status_code, 400)
        expected = {'error': error_msg}
        self.assertDictEqual(json.loads(response.content), expected)

    def test_missing_basket(self):
        """ Verify the view returns an HTTP 400 status if the basket is missing. """
        self.assert_basket_retrieval_error(1234)

    def test_mismatched_basket_owner(self):
        """ Verify the view returns an HTTP 400 status if the posted basket does not belong to the requesting user. """
        basket = factories.BasketFactory()
        self.assert_basket_retrieval_error(basket.id)

        basket = factories.BasketFactory(owner=self.create_user())
        self.assert_basket_retrieval_error(basket.id)

    @ddt.data(Basket.MERGED, Basket.SAVED, Basket.FROZEN, Basket.SUBMITTED)
    def test_invalid_basket_status(self, status):
        """ Verify the view returns an HTTP 400 status if the basket is in an invalid state. """
        basket = factories.BasketFactory(owner=self.user, status=status)
        error_msg = 'Your basket may have been modified or already purchased. Refresh the page to try again.'
        self._assert_basket_error(basket.id, error_msg)

    @freeze_time('2016-01-01')
    def test_valid_request(self):
        """ Verify the view returns the CyberSource parameters if the request is valid. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], JSON)

        actual = json.loads(response.content)['form_fields']
        transaction_uuid = actual['transaction_uuid']
        extra_parameters = {
            'payment_method': 'card',
            'unsigned_field_names': 'card_cvn,card_expiry_date,card_number,card_type',
            'bill_to_email': self.user.email,
            'device_fingerprint_id': self.client.session.session_key,
            'bill_to_address_city': data['city'],
            'bill_to_address_country': data['country'],
            'bill_to_address_line1': data['address_line1'],
            'bill_to_address_line2': data['address_line2'],
            'bill_to_address_postal_code': data['postal_code'],
            'bill_to_address_state': data['state'],
            'bill_to_forename': data['first_name'],
            'bill_to_surname': data['last_name'],
        }

        expected = self.get_expected_transaction_parameters(
            basket,
            transaction_uuid,
            use_sop_profile=True,
            extra_parameters=extra_parameters
        )
        self.assertDictEqual(actual, expected)

        # Ensure the basket is frozen
        basket = Basket.objects.get(pk=basket.pk)
        self.assertEqual(basket.status, Basket.FROZEN)

    def test_field_error(self):
        """ Verify the view responds with a JSON object containing fields with errors, when input is invalid. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        field = 'first_name'
        del data[field]

        response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['content-type'], JSON)

        errors = json.loads(response.content)['field_errors']
        self.assertIn(field, errors)
