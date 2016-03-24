import ddt
from django.conf import settings
from django.test import override_settings
import mock

from ecommerce.core.exceptions import MissingRequestError
from ecommerce.core.tests import toggle_switch
from ecommerce.extensions.payment import helpers
from ecommerce.extensions.payment.exceptions import ProcessorNotFoundError
from ecommerce.extensions.payment.tests.processors import DummyProcessor, AnotherDummyProcessor
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

    @staticmethod
    def _enable_processor_switches(processors):
        for processor in processors:
            toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + processor.NAME, True)

    @ddt.data(
        ([], []),
        ([DummyProcessor], [DummyProcessor]),
        ([DummyProcessor, AnotherDummyProcessor], [DummyProcessor, AnotherDummyProcessor]),
    )
    @ddt.unpack
    def test_get_payment_processors(self, processors, expected_result):
        self._enable_processor_switches(processors)
        mock_req = mock.Mock()
        mock_req.site.siteconfiguration.allowed_payment_processors = {proc.NAME for proc in processors}

        with mock.patch('ecommerce.extensions.payment.helpers.get_current_request', mock.Mock(return_value=mock_req)):
            result = helpers.get_payment_processors()
            self.assertEqual(result, expected_result)

    @override_settings(PAYMENT_PROCESSORS=[
        'ecommerce.extensions.payment.tests.processors.DummyProcessor',
    ])
    @ddt.data(
        ([], []),
        ([DummyProcessor], [DummyProcessor]),
        ([DummyProcessor, AnotherDummyProcessor], [DummyProcessor]),
    )
    @ddt.unpack
    def test_get_payment_processors_single_processor_in_config(self, processors, expected_result):
        self._enable_processor_switches(processors)
        mock_req = mock.Mock()
        mock_req.site.siteconfiguration.allowed_payment_processors = {proc.NAME for proc in processors}

        with mock.patch('ecommerce.extensions.payment.helpers.get_current_request', mock.Mock(return_value=mock_req)):
            result = helpers.get_payment_processors()
            self.assertEqual(result, expected_result)

    @ddt.data(
        [DummyProcessor],
        [DummyProcessor, AnotherDummyProcessor]
    )
    def test_get_payment_processors_switch_disabled(self, processors):
        mock_req = mock.Mock()
        mock_req.site.siteconfiguration.allowed_payment_processors = {proc.NAME for proc in processors}
        expected_result = []

        with mock.patch('ecommerce.extensions.payment.helpers.get_current_request', mock.Mock(return_value=mock_req)):
            result = helpers.get_payment_processors()
            self.assertEqual(result, expected_result)

    def test_get_payment_processors_no_request(self):
        with mock.patch('ecommerce.extensions.payment.helpers.get_current_request', mock.Mock(return_value=None)):
            with self.assertRaises(MissingRequestError):
                helpers.get_payment_processors()
