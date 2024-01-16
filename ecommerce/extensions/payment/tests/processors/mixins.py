# -*- coding: utf-8 -*-
"""Base class for payment processor implementation test classes."""


import ddt
from django.conf import settings
from oscar.core.loading import get_model

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.extensions.test.factories import create_basket
from ecommerce.tests.factories import SiteConfigurationFactory, UserFactory

Partner = get_model('partner', 'Partner')


@ddt.ddt
class PaymentProcessorTestCaseMixin(RefundTestMixin, DiscoveryTestMixin, PaymentEventsMixin):
    """ Mixin for payment processor tests. """

    # Subclasses should set this value. It will be used to instantiate the processor in setUp.
    processor_class = None

    # This value is used to test the NAME attribute on the processor.
    processor_name = None

    CERTIFICATE_TYPE = 'test-certificate-type'
    CLIENT_SIDE_PAYMENT_ENABLED_PROCESSORS = ['android-iap', 'ios-iap']

    def setUp(self):
        super(PaymentProcessorTestCaseMixin, self).setUp()

        self.course = CourseFactory(id='a/b/c', name='Demo Course', partner=self.partner)
        self.product = self.course.create_or_update_seat(self.CERTIFICATE_TYPE, False, 20)

        self.processor = self.processor_class(self.site)  # pylint: disable=not-callable
        self.basket = create_basket(site=self.site, owner=UserFactory(), empty=True)
        self.basket.add_product(self.product)

    def test_configuration(self):
        """ Verifies configuration is read from settings. """
        other_site = SiteConfigurationFactory(partner__short_code='other').site

        for site in (self.site, other_site):
            processor = self.processor_class(site)  # pylint: disable=not-callable
            short_code = site.siteconfiguration.partner.short_code.lower()
            self.assertDictEqual(
                processor.configuration,
                settings.PAYMENT_PROCESSOR_CONFIG[short_code][processor.NAME.lower()]
            )

    def test_name(self):
        """Test that the name constant on the processor class is correct."""
        self.assertEqual(self.processor.NAME, self.processor_name)

    def test_client_side_payment_url(self):
        """ Verify the property returns the client-side payment URL. """
        if self.processor.NAME in self.CLIENT_SIDE_PAYMENT_ENABLED_PROCESSORS:
            self.assertIsNotNone(self.processor.client_side_payment_url)
        else:
            self.assertIsNone(self.processor.client_side_payment_url)

    def test_get_transaction_parameters(self):
        """ Verify the processor returns the appropriate parameters required to complete a transaction. """
        raise NotImplementedError

    def test_handle_processor_response(self):
        """ Verify that the processor creates the appropriate PaymentEvent and Source objects. """
        raise NotImplementedError

    def test_issue_credit(self):
        """ Verify the payment processor responds appropriately to requests to issue credit/refund. """
        raise NotImplementedError

    def test_issue_credit_error(self):
        """ Verify the payment processor responds appropriately if the payment gateway cannot issue a credit/refund. """
        raise NotImplementedError
