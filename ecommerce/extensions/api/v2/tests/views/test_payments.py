import json

from django.conf import settings
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test import override_settings
from waffle.models import Switch

from ecommerce.extensions.payment.tests.processors import DummyProcessor, AnotherDummyProcessor
from ecommerce.tests.testcases import TestCase


class PaymentProcessorListViewTests(TestCase):
    """ Ensures correct behavior of the payment processors list view."""

    def setUp(self):
        super(PaymentProcessorListViewTests, self).setUp()
        self.token = self.generate_jwt_token_header(self.create_user())
        self.toggle_payment_processor('dummy', True)
        self.toggle_payment_processor('another-dummy', True)
        # Clear the view cache
        cache.clear()

    def toggle_payment_processor(self, processor, active):
        """Set the given payment processor's Waffle switch."""
        switch, __ = Switch.objects.get_or_create(name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + processor)
        switch.active = active
        switch.save()

    def assert_processor_list_matches(self, expected):
        """ DRY helper. """
        response = self.client.get(reverse('api:v2:payment:list_processors'), HTTP_AUTHORIZATION=self.token)
        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(set(json.loads(response.content)), set(expected))

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
        self.toggle_payment_processor('dummy', False)
        self.assert_processor_list_matches([])

    @override_settings(PAYMENT_PROCESSORS=[
        'ecommerce.extensions.payment.tests.processors.DummyProcessor',
        'ecommerce.extensions.payment.tests.processors.AnotherDummyProcessor',
    ])
    def test_waffle_switches_clear_cache(self):
        self.assert_processor_list_matches([DummyProcessor.NAME, AnotherDummyProcessor.NAME])
        self.toggle_payment_processor('dummy', False)
        self.assert_processor_list_matches([AnotherDummyProcessor.NAME])
