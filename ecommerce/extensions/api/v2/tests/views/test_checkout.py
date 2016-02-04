from __future__ import unicode_literals

import json

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import override_settings
from oscar.core.loading import get_model
from waffle.models import Switch

from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')


class DummyProcessorWithUrl(DummyProcessor):
    """ Dummy payment processor class that has a test payment page url. """
    NAME = 'dummy_with_url'

    def get_transaction_parameters(self, basket, request=None):
        dummy_values = {
            'payment_page_url': 'test_processor.edx',
            'transaction_param': 'test_trans_param'
        }
        return dummy_values


@override_settings(
    PAYMENT_PROCESSORS=['ecommerce.extensions.api.v2.tests.views.test_checkout.DummyProcessorWithUrl']
)
class CheckoutViewTests(TestCase):
    """ Tests for CheckoutView API view. """
    path = reverse('api:v2:checkout')

    def setUp(self):
        super(CheckoutViewTests, self).setUp()
        self.activate_payment_processor()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        Basket.objects.create(owner=self.user)
        self.data = {
            'basket_id': 1,
            'payment_processor': DummyProcessorWithUrl.NAME
        }

    def activate_payment_processor(self):
        """ Helper function to activate the dummy payment processor. """
        switch, __ = Switch.objects.get_or_create(
            name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + DummyProcessorWithUrl.NAME
        )
        switch.active = True
        switch.save()

    def test_authentication_required(self):
        """ Verify the endpoint requires authentication. """
        self.client.logout()
        response = self.client.post(self.path, data=self.data)
        self.assertEqual(response.status_code, 401)

    def test_no_basket(self):
        """ Verify the endpoint returns HTTP 400 if the user has no associated baskets. """
        self.user.baskets.all().delete()
        response = self.client.post(self.path, data=self.data)
        self.assertEqual(response.status_code, 400)

    def test_view_response(self):
        """ Verify the endpoint returns a successful response when the user is able to checkout. """
        response = self.client.post(self.path, data=self.data)
        self.assertEqual(response.status_code, 200)

        response_data = json.loads(response.content)
        self.assertEqual(response_data['payment_form_data']['transaction_param'], 'test_trans_param')
        self.assertEqual(response_data['payment_page_url'], 'test_processor.edx')
        self.assertEqual(response_data['payment_processor'], 'dummy_with_url')
