

import ddt
from django.test import override_settings

from ecommerce.extensions.payment import helpers
from ecommerce.extensions.payment.exceptions import ProcessorNotFoundError
from ecommerce.extensions.payment.tests.processors import AnotherDummyProcessor, DummyProcessor
from ecommerce.tests.testcases import TestCase


@ddt.ddt
@override_settings(PAYMENT_PROCESSORS=[
    'ecommerce.extensions.payment.tests.processors.DummyProcessor',
    'ecommerce.extensions.payment.tests.processors.AnotherDummyProcessor',
])
class HelperTests(TestCase):
    def test_get_processor_class(self):
        """ Verify that the method retrieves the correct class. """
        actual = helpers.get_processor_class('ecommerce.extensions.payment.tests.processors.DummyProcessor')
        self.assertIs(actual, DummyProcessor)

    def test_get_default_processor_class(self):
        """ Verify the function returns the first processor class defined in settings. """
        self.assertIs(helpers.get_default_processor_class(), DummyProcessor)

    @ddt.data(DummyProcessor, AnotherDummyProcessor)
    def test_get_processor_class_by_name(self, processor):
        """ Verify the function returns the appropriate processor class or raises an exception, if not found. """
        self.assertIs(helpers.get_processor_class_by_name(processor.NAME), processor)

    def test_get_processor_class_by_name_not_found(self):
        """
        If get_processor_class_by_name is called with the name of a non-existent processor,
        ProcessorNotFoundError should be raised.
        """
        self.assertRaises(ProcessorNotFoundError, helpers.get_processor_class_by_name, 'foo')

    def test_sign(self):
        """ Verify the function returns a valid HMAC SHA-256 signature. """
        message = "This is a super-secret message!"
        secret = "password"
        expected = "qU4fRskS/R9yZx/yPq62sFGOUzX0GSUtmeI6bPVsqao="
        self.assertEqual(helpers.sign(message, secret), expected)
