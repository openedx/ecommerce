

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from edx_django_utils.cache import TieredCache

from ecommerce.core.models import SiteConfiguration
from ecommerce.core.tests import toggle_switch
from ecommerce.extensions.payment.tests.processors import AnotherDummyProcessor, DummyProcessor
from ecommerce.tests.testcases import TestCase


class PaymentProcessorListViewTests(TestCase):
    """ Ensures correct behavior of the payment processors list view."""

    def setUp(self):
        super(PaymentProcessorListViewTests, self).setUp()
        self.token = self.generate_jwt_token_header(self.create_user())
        toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + DummyProcessor.NAME, True)
        toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + AnotherDummyProcessor.NAME, True)

        site_config, __ = SiteConfiguration.objects.get_or_create(site__id=1)

        old_payment_processors = site_config.payment_processors
        site_config.payment_processors = ",".join([DummyProcessor.NAME, AnotherDummyProcessor.NAME])
        site_config.save()

        def reset_site_config():
            """ Reset method - resets site_config to pre-test state """
            site_config.payment_processors = old_payment_processors
            site_config.save()

        self.addCleanup(reset_site_config)

        # Clear the view cache
        TieredCache.dangerous_clear_all_tiers()

    def assert_processor_list_matches(self, expected):
        """ DRY helper. """
        response = self.client.get(reverse('api:v2:payment:list_processors'), HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(set(response.json()), set(expected))

    def test_permission(self):
        """Ensure authentication is required to access the view. """
        response = self.client.get(reverse('api:v2:payment:list_processors'))
        self.assertEqual(response.status_code, 401)

    @override_settings(PAYMENT_PROCESSORS=['ecommerce.extensions.payment.tests.processors.DummyProcessor'])
    def test_get_one(self):
        """Ensure a single payment processor in settings is handled correctly."""
        self.assert_processor_list_matches([DummyProcessor.NAME])

    @override_settings(PAYMENT_PROCESSORS=[
        'ecommerce.extensions.payment.tests.processors.DummyProcessor',
        'ecommerce.extensions.payment.tests.processors.AnotherDummyProcessor',
    ])
    def test_get_many(self):
        """Ensure multiple processors in settings are handled correctly."""
        self.assert_processor_list_matches([DummyProcessor.NAME, AnotherDummyProcessor.NAME])

    @override_settings(PAYMENT_PROCESSORS=[
        'ecommerce.extensions.payment.tests.processors.DummyProcessor',
    ])
    def test_processor_disabled(self):
        """  Tests that disabloing payment processor works """
        toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + DummyProcessor.NAME, False)
        self.assert_processor_list_matches([])

    @override_settings(PAYMENT_PROCESSORS=[
        'ecommerce.extensions.payment.tests.processors.DummyProcessor',
        'ecommerce.extensions.payment.tests.processors.AnotherDummyProcessor',
    ])
    def test_waffle_switches_clear_cache(self):
        """ Tests that adding a new Switch resets processor cache """
        self.assert_processor_list_matches([DummyProcessor.NAME, AnotherDummyProcessor.NAME])
        toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + DummyProcessor.NAME, False)
        self.assert_processor_list_matches([AnotherDummyProcessor.NAME])
