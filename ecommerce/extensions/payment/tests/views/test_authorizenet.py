import json
import base64
from mock import patch
from lxml import objectify
from django.urls import reverse
from oscar.test import factories
from oscar.core.loading import get_class, get_model

from ecommerce.tests.testcases import TestCase
from ecommerce.core.url_utils import get_lms_dashboard_url
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.test.factories import create_basket
from ecommerce.extensions.test.authorizenet_utils import (
    get_authorizenet_transaction_reponse_xml,
)
from ecommerce.extensions.test.constants import (
    transaction_detail_response_success_data,
)
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.api.v2.tests.views import JSON_CONTENT_TYPE
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.extensions.payment.processors.authorizenet import AuthorizeNet
from ecommerce.extensions.payment.exceptions import MissingTransactionDetailError
from ecommerce.extensions.payment.views.authorizenet import AuthorizeNetNotificationView


Country = get_model('address', 'Country')
Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
Source = get_model('payment', 'Source')
Product = get_model('catalogue', 'Product')

NOTIFICATION_TYPE_AUTH_CAPTURE = 'net.authorize.payment.authcapture.created'


class AuthorizeNetNotificationViewTests(PaymentEventsMixin, TestCase):
    path = reverse('authorizenet:authorizenet_notifications')

    def setUp(self):
        super(AuthorizeNetNotificationViewTests, self).setUp()
        self.user = self.create_user()
        self.course = CourseFactory(partner=self.partner)
        self.view = AuthorizeNetNotificationView()
        self.transaction_id = "1111111111111111"
        self.country_name = "UNITED KINGDOM"

    def get_notification_response(self, responseCode, event_type=NOTIFICATION_TYPE_AUTH_CAPTURE, transaction_id=None):
        """
            return notification view response
        """
        notification = {
            'notificationId':'fake_id',
            'eventType': event_type,
            'eventDate': 'some_date',
            'webhookId':'fake_webhook_id',
            'payload': {
                'responseCode': responseCode,
                'authCode': 'fake_code',
                'avsResponse': 'Y',
                'authAmount': 100.00,
                'entityName': 'transaction',
            }
        }
        if transaction_id:
            notification.get('payload').update({'id': transaction_id})

        response = self.client.post(self.path, json.dumps(notification), JSON_CONTENT_TYPE)
        return response

    def create_basket_with_product(self):
        """
            creates a frozen basket with a product.
        """
        product = self.course.create_or_update_seat('verified', True, 100)
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(product, 1)
        basket.freeze()
        return basket

    def assert_order_created(self, basket, card_type, label):
        """
            Verify order placement and payment event.
        """
        order = Order.objects.get(number=basket.order_number, total_incl_tax=basket.total_incl_tax)
        total = order.total_incl_tax
        order.payment_events.get(event_type__code='paid', amount=total)
        Source.objects.get(
            source_type__name=AuthorizeNet.NAME,
            currency=order.currency,
            amount_allocated=total,
            amount_debited=total,
            card_type=card_type,
            label=label
        )
        PaymentEvent.objects.get(
            event_type__name=PaymentEventTypeName.PAID,
            amount=total,
            processor_name=AuthorizeNet.NAME
        )

    @patch('ecommerce.extensions.payment.views.authorizenet.logger', autospec=True)
    def test_notification_for_other_event_type(self, mock_logger):
        """
            Test received notification for an event containing event-type other than auth capture.
        """
        event_type = 'other_event_types'
        response = self.get_notification_response(
            event_type=event_type,
            responseCode=1,
            transaction_id=self.transaction_id
        )
        expected_error_meassage = (
            'Received AuthroizeNet notifciation with event_type [%s]. Currently, '
            'We are not handling such type of notifications.'
        )
        self.assertEqual(response.status_code, 204)
        mock_logger.error.assert_called_once_with(expected_error_meassage, event_type)

    @patch('ecommerce.extensions.payment.views.authorizenet.logger', autospec=True)
    def test_notification_without_transaction_id(self, mock_logger):
        """
            Test received notification with no transaction_id.
        """
        response = self.get_notification_response(responseCode=1)
        self.assertEqual(response.status_code, 400)
        mock_logger.error.assert_called_once_with(
            'Recieved AuthorizeNet transaction notification without transaction_id')

    @patch('ecommerce.extensions.payment.views.authorizenet.logger', autospec=True)
    @patch('ecommerce.extensions.payment.views.authorizenet.AuthorizeNetNotificationView.payment_processor', autospec=True)
    def test_notification_without_transaction_details(self, mock_processor, mock_logger):
        """
            Test received notification with transaction_id for which we are unable to fetch transcation_details.
        """
        mock_processor.get_transaction_detail.side_effect = MissingTransactionDetailError
        response = self.get_notification_response(
            responseCode=1,
            transaction_id=self.transaction_id
        )

        mock_processor.get_transaction_detail.assert_called_once_with(self.transaction_id)
        self.assertEqual(response.status_code, 200)
        mock_logger.exception.assert_called_once_with(
            'An error occurred while processing the AuthorizeNet payment for transaction_id [%s].',
            self.transaction_id
        )

    @patch('ecommerce.extensions.payment.views.authorizenet.send_notification', autospec=True)
    @patch('ecommerce.extensions.payment.processors.authorizenet.getTransactionDetailsController', autospec=True)
    def test_notification_declined_transaction(self, mock_controller, mock_email):
        """
            Test received notification of a declined transaction.
        """
        basket = self.create_basket_with_product()
        response_data = transaction_detail_response_success_data

        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(self.transaction_id, basket, response_data)
        transaction_detail_response = objectify.fromstring(transaction_detail_xml)
        mock_controller.return_value.getresponse.return_value = transaction_detail_response

        response = self.get_notification_response(
            responseCode=2,
            transaction_id=self.transaction_id
        )

        self.assertEqual(response.status_code, 200)
        mock_email.assert_called_once_with(
            basket.owner,
            'TRANSACTION_REJECTED',
            {
                'course_title': basket.all_lines()[0].product.title,
                'transaction_status': 'Declined',
            },
            basket.site
        )
        self.assertFalse( Order.objects.filter(number=basket.order_number, total_incl_tax=basket.total_incl_tax).exists())

    @patch('ecommerce.extensions.payment.views.authorizenet.send_notification', autospec=True)
    @patch('ecommerce.extensions.payment.processors.authorizenet.getTransactionDetailsController', autospec=True)
    def test_notification_error_transaction(self, mock_controller, mock_email):
        """
            Test received notification of an error transaction.
        """
        basket = self.create_basket_with_product()
        response_data = transaction_detail_response_success_data

        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
            self.transaction_id, basket, response_data)
        transaction_detail_response = objectify.fromstring(transaction_detail_xml)
        mock_controller.return_value.getresponse.return_value = transaction_detail_response

        response = self.get_notification_response(
            responseCode=3,
            transaction_id=self.transaction_id
        )

        self.assertEqual(response.status_code, 200)
        mock_email.assert_called_once_with(
            basket.owner,
            'TRANSACTION_REJECTED',
            {
                'course_title': basket.all_lines()[0].product.title,
                'transaction_status': 'Error',
            },
            basket.site
        )
        self.assertFalse( Order.objects.filter(number=basket.order_number, total_incl_tax=basket.total_incl_tax).exists())

    @patch('ecommerce.extensions.payment.views.authorizenet.logger', autospec=True)
    @patch('ecommerce.extensions.payment.views.authorizenet.OrderNumberGenerator.basket_id', autospec=True)
    @patch('ecommerce.extensions.payment.processors.authorizenet.getTransactionDetailsController', autospec=True)
    def test_notification_for_invalid_basket(self, mock_controller, mock_basket_id, mock_logger):
        """
            Test received notification for an invalid basket id.
        """
        basket = self.create_basket_with_product()
        response_data = transaction_detail_response_success_data

        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
            self.transaction_id, basket, response_data)
        transaction_detail_response = objectify.fromstring(transaction_detail_xml)

        mock_controller.return_value.getresponse.return_value = transaction_detail_response
        basket_id = "invalid_basket_id"
        mock_basket_id.return_value = basket_id

        response = self.get_notification_response(
            responseCode=3,
            transaction_id=self.transaction_id
        )

        self.assertEqual(response.status_code, 200)
        mock_logger.error.assert_called_once_with(
            'Received AuthorizeNet payment notification for non-existent basket [%s].',
            basket_id
        )
        self.assertFalse( Order.objects.filter(number=basket.order_number, total_incl_tax=basket.total_incl_tax).exists())

    @patch('ecommerce.extensions.payment.processors.authorizenet.getTransactionDetailsController', autospec=True)
    def test_notification_success_transaction(self, mock_controller):
        """
            Test received notification success scenerio.
        """
        basket = self.create_basket_with_product()
        response_data = transaction_detail_response_success_data

        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
            self.transaction_id, basket, response_data)
        transaction_detail_response = objectify.fromstring(transaction_detail_xml)
        mock_controller.return_value.getresponse.return_value = transaction_detail_response

        response = self.get_notification_response(
            responseCode=1,
            transaction_id=self.transaction_id
        )

        card_info = transaction_detail_response.transaction.payment.creditCard

        self.assertEqual(response.status_code, 200)
        self.assert_order_created(basket, card_info.cardType, card_info.cardNumber)

    @patch('ecommerce.extensions.payment.views.authorizenet.send_notification', autospec=True)
    def test_send_transaction_declined_email(self, mock_email):
        """
            Test declined transcations email function.
        """
        basket = self.create_basket_with_product()
        course_title = basket.all_lines()[0].product.title
        transaction_status = 'fake_transcation_status'
        self.view._send_transaction_declined_email(basket, transaction_status, course_title)
        mock_email.assert_called_once_with(
            basket.owner,
            'TRANSACTION_REJECTED',
            {
                'course_title': course_title,
                'transaction_status': transaction_status,
            },
            basket.site
        )

    def test_get_basket(self):
        """
            Verify that basket has been retrieved properly.
        """
        expected_basket = self.create_basket_with_product()
        actual_basket = self.view._get_basket(expected_basket.id)
        self.assertEqual(actual_basket, expected_basket)

    def test_get_basket_for_invalid_id(self):
        """
            Verify that function returns None if there is no basket
        """
        expected_basket = None
        actual_basket = self.view._get_basket("invalid_basket_id")
        self.assertEqual(actual_basket, expected_basket)

    def test_get_billing_address(self):
        """
            Verify that Billing address object is returning proprly containing required information.
        """
        basket = self.create_basket_with_product()

        response_data = transaction_detail_response_success_data
        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
            self.transaction_id, basket, response_data)
        transaction_detail_response = objectify.fromstring(transaction_detail_xml)

        transaction_bill = transaction_detail_response.transaction.billTo
        order_number = str(transaction_detail_response.transaction.order.invoiceNumber)

        actual_billing_address = self.view._get_billing_address(transaction_bill, order_number, basket)

        self.assertEqual(actual_billing_address.first_name, transaction_bill.firstName)
        self.assertEqual(actual_billing_address.last_name, transaction_bill.lastName)
        self.assertEqual(actual_billing_address.line1, '')
        self.assertEqual(actual_billing_address.state, '')
        self.assertEqual(actual_billing_address.country.printable_name, self.country_name)

    @patch('ecommerce.extensions.payment.views.authorizenet.logger')
    def test_get_billing_address_exception(self, mock_logger):
        """
            Verify that funtion is rturning None and log proper error in case of exception.
        """
        basket = self.create_basket_with_product()

        response_data = transaction_detail_response_success_data
        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
            self.transaction_id, basket, response_data)
        transaction_detail_response = objectify.fromstring(transaction_detail_xml)

        transaction_bill = transaction_detail_response.transaction.billTo
        order_number = str(transaction_detail_response.transaction.order.invoiceNumber)

        Country.objects.filter(iso_3166_1_a2__iexact=transaction_bill.country).delete()
        actual_billing_address = self.view._get_billing_address(transaction_bill, order_number, basket)

        self.assertEqual(actual_billing_address, None)
        expected_exception_msg = (
            'An error occurred while parsing the billing address for basket [%d]. '
            'No billing address will be stored for the resulting order [%s].'
        )
        mock_logger.exception.assert_called_once_with(expected_exception_msg, basket.id, order_number)

    def test_call_handle_order_placement(self):
        """
            Verify that funtion is placing order properly.
        """
        basket = self.create_basket_with_product()

        response_data = transaction_detail_response_success_data
        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
            self.transaction_id, basket, response_data)
        transaction_detail_response = objectify.fromstring(transaction_detail_xml)

        self.view._call_handle_order_placement(basket, self.client, transaction_detail_response)
        Order.objects.get(number=basket.order_number, total_incl_tax=basket.total_incl_tax)

    @patch('ecommerce.extensions.payment.views.authorizenet.AuthorizeNetNotificationView.log_order_placement_exception')
    @patch('ecommerce.extensions.payment.views.authorizenet.OrderTotalCalculator.calculate')
    def test_call_handle_order_placement_exception(self, mock_order_calculator, mock_logger_function):
        """
            Verify that function do not place an order in case of exception
        """
        basket = self.create_basket_with_product()

        response_data = transaction_detail_response_success_data
        transaction_detail_xml = get_authorizenet_transaction_reponse_xml(
            self.transaction_id, basket, response_data)
        transaction_detail_response = objectify.fromstring(transaction_detail_xml)

        mock_order_calculator.side_effect = Exception

        self.view._call_handle_order_placement(basket, self.client, transaction_detail_response)
        mock_logger_function.assert_called_once_with(basket.order_number, basket.id)
        self.assertFalse(Order.objects.filter(number=basket.order_number, total_incl_tax=basket.total_incl_tax).exists())


class AuthorizeNetRedirectionViewTests(TestCase):
    path = reverse('authorizenet:redirect')

    def test_handle_redirection(self):
        """
            Verify redirection with proper cookie.
        """
        expected_course_id = "fake_course_id"
        course_id_hash = base64.b64encode(expected_course_id.encode())
        url = '{}?course={}'.format(self.path, course_id_hash )
        response = self.client.get(url)

        actual_course_id_hash = response.cookies.get('pendingTransactionCourse').value
        actual_course_id = base64.b64decode(actual_course_id_hash)

        self.assertEqual(actual_course_id, expected_course_id)
        self.assertRedirects(
            response, get_lms_dashboard_url(), fetch_redirect_response=False)
