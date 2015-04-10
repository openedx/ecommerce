""" Tests of the Payment Views. """
import json

from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.utils import override_settings
from oscar.test import factories
from oscar.core.loading import get_model

from ecommerce.extensions.payment.constants import ProcessorConstants as PC
from ecommerce.extensions.payment.processors import BasePaymentProcessor
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.tests.mixins import UserMixin


ShippingEventType = get_model('order', 'ShippingEventType')
Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')

ORDER_NUMBER = '001'

FAILURE_PROCESSOR = 'ecommerce.extensions.payment.tests.test_views.DummyGenericFailureProcessor'
ERROR_FAILURE_PROCESSOR = 'ecommerce.extensions.payment.tests.test_views.DummyErrorFailureProcessor'
SUCCESS_PROCESSOR = 'ecommerce.extensions.payment.tests.test_views.DummySuccessProcessor'


class DummyGenericFailureProcessor(BasePaymentProcessor):
    """ Mocks out a failure response from the processor. """
    NAME = 'DummyFailureProcessor'

    def get_transaction_parameters(
            self,
            order,
            receipt_page_url=None,
            cancel_page_url=None,
            merchant_defined_data=None
    ):
        """Generate a dictionary of transaction parameters to be sent to a payment processor."""
        pass

    def handle_processor_response(self, params):
        """ Return the expected output. """
        return {PC.SUCCESS: False, PC.ORDER_NUMBER: None}


class DummyErrorFailureProcessor(BasePaymentProcessor):
    """ Mocks out a failure response from the processor when we also receive an error. """
    NAME = 'DummyFailureProcessor'

    def get_transaction_parameters(
            self,
            order,
            receipt_page_url=None,
            cancel_page_url=None,
            merchant_defined_data=None
    ):
        """Generate a dictionary of transaction parameters to be sent to a payment processor."""
        pass

    def handle_processor_response(self, params):
        """ Return the expected output. """
        order = Order.objects.get(number=ORDER_NUMBER)
        order.set_status(ORDER.PAYMENT_ERROR)
        return {PC.SUCCESS: False, PC.ORDER_NUMBER: None}


class DummySuccessProcessor(BasePaymentProcessor):
    """ Mocks out a success response from the processor. """
    NAME = 'DummySuccessProcessor'

    def get_transaction_parameters(
            self,
            order,
            receipt_page_url=None,
            cancel_page_url=None,
            merchant_defined_data=None
    ):
        """Generate a dictionary of transaction parameters to be sent to a payment processor."""
        pass

    def handle_processor_response(self, params):
        """ Return the expected output. """
        return {PC.SUCCESS: True, PC.ORDER_NUMBER: ORDER_NUMBER}


class ProcessorListViewTestCase(TestCase, UserMixin):
    """ Ensures correct behavior of the payment processors list view."""

    def setUp(self):
        self.token = self.generate_jwt_token_header(self.create_user())

    def assert_processor_list_matches(self, expected):
        """ DRY helper. """
        response = self.client.get(reverse('processor_list'), HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(set(json.loads(response.content)), set(expected))

    def test_permission(self):
        """Ensure authentication is required to access the view. """
        response = self.client.get(reverse('processor_list'))
        self.assertEqual(response.status_code, 401)

    @override_settings(PAYMENT_PROCESSORS=[SUCCESS_PROCESSOR])
    def test_get_one(self):
        """Ensure a single payment processor in settings is handled correctly."""
        self.assert_processor_list_matches(['DummySuccessProcessor'])

    @override_settings(PAYMENT_PROCESSORS=[SUCCESS_PROCESSOR, FAILURE_PROCESSOR])
    def test_get_many(self):
        """Ensure multiple processors in settings are handled correctly."""
        self.assert_processor_list_matches(['DummySuccessProcessor', 'DummyFailureProcessor'])


# Reuse the fake fulfillment module provided by the test_api tests
@override_settings(
    FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.test_api.FakeFulfillmentModule', ]
)
class CybersoureResponseViewTestCase(TestCase):
    """ Tests of the CybersourceResponseView. """

    def setUp(self):
        self.user = factories.UserFactory(username='edx')
        self.order = factories.create_order(number=ORDER_NUMBER, status=ORDER.BEING_PROCESSED)
        # Create a type of event that gets used during fulfillment
        ShippingEventType.objects.create(code='shipped', name='Shipped')
        PaymentEventType.objects.create(name=PC.PAID_EVENT_NAME)

    @override_settings(
        PAYMENT_PROCESSORS=[SUCCESS_PROCESSOR],
    )
    def test_handle_successful_response(self):
        """ Check that on successful processing, we are recording and fulfilling correctly."""
        self.client.post(reverse('cybersource_callback'), params='{}')

        # Even though this goes through FakeFulfillmentModule, make sure that
        # the FakeFulfillmentModule did get called on this order
        order = Order.objects.get(number=ORDER_NUMBER)
        self.assertEquals(order.status, ORDER.COMPLETE)

        # Ensure that the payment event was also recorded
        event_type = PaymentEventType.objects.get(name=PC.PAID_EVENT_NAME)
        events = PaymentEvent.objects.filter(event_type=event_type)
        self.assertGreater(events.count(), 0)
        for event in events:
            self.assertEquals(event.amount, order.total_excl_tax)
            self.assertEquals(event.reference, order.number)

    @override_settings(
        PAYMENT_PROCESSORS=[FAILURE_PROCESSOR],
    )
    def test_handle_failed_response(self):
        """ Check that things are still in the correct state when the payment has failed. """
        self.client.post(reverse('cybersource_callback'), params='{}')
        order = Order.objects.get(number=ORDER_NUMBER)
        self.assertEquals(order.status, ORDER.BEING_PROCESSED)

        event_type = PaymentEventType.objects.get(name=PC.PAID_EVENT_NAME)
        events = PaymentEvent.objects.filter(event_type=event_type)
        self.assertEquals(events.count(), 0)

    @override_settings(
        PAYMENT_PROCESSORS=[ERROR_FAILURE_PROCESSOR],
    )
    def test_handle_failed_error_response(self):
        """
        Check that things are still in the correct state when the payment has failed,
        and the processor has passed us an error.
        """
        self.client.post(reverse('cybersource_callback'), params='{}')
        order = Order.objects.get(number=ORDER_NUMBER)
        self.assertEquals(order.status, ORDER.PAYMENT_ERROR)

        event_type = PaymentEventType.objects.get(name=PC.PAID_EVENT_NAME)
        events = PaymentEvent.objects.filter(event_type=event_type)
        self.assertEquals(events.count(), 0)
