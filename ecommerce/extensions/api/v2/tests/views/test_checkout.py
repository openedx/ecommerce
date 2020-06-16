

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from oscar.core.loading import get_model

from ecommerce.core.tests import toggle_switch
from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')


class DummyProcessorWithUrl(DummyProcessor):
    """ Dummy payment processor class that has a test payment page url. """
    NAME = 'dummy_with_url'

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        dummy_values = {
            'payment_page_url': 'test_processor.edx',
            'transaction_param': 'test_trans_param'
        }
        return dummy_values


class CheckoutViewTests(TestCase):
    """ Tests for CheckoutView API view. """
    path = reverse('api:v2:checkout:process')

    def setUp(self):
        super(CheckoutViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.basket = Basket.objects.create(site=self.site, owner=self.user)
        self.data = {
            'basket_id': self.basket.id,
            'payment_processor': DummyProcessorWithUrl.NAME
        }

    def test_authentication_required(self):
        """ Verify the endpoint requires authentication. """
        self.client.logout()
        response = self.client.post(self.path, data=self.data)
        self.assertEqual(response.status_code, 401)

    def test_no_basket(self):
        """ Verify the endpoint returns HTTP 400 if the user has no associated baskets. """
        self.user.baskets.all().delete()
        expected_content = 'Basket [{}] not found.'.format(self.data['basket_id'])
        response = self.client.post(self.path, data=self.data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode('utf-8'), expected_content)

    def test_invalid_payment_processor(self):
        """ Verify the endpoint returns HTTP 400 if payment processor not found. """
        expected_content = 'Payment processor [{}] not found.'.format(DummyProcessorWithUrl.NAME)
        response = self.client.post(self.path, data=self.data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content.decode('utf-8'), expected_content)

    @override_settings(
        PAYMENT_PROCESSORS=['ecommerce.extensions.api.v2.tests.views.test_checkout.DummyProcessorWithUrl']
    )
    def test_view_response(self):
        """ Verify the endpoint returns a successful response when the user is able to checkout. """
        toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + DummyProcessorWithUrl.NAME, True)
        response = self.client.post(self.path, data=self.data)
        self.assertEqual(response.status_code, 200)

        basket = Basket.objects.get(id=self.basket.id)
        self.assertEqual(basket.status, Basket.FROZEN)
        response_data = response.json()
        self.assertEqual(response_data['payment_form_data']['transaction_param'], 'test_trans_param')
        self.assertEqual(response_data['payment_page_url'], 'test_processor.edx')
        self.assertEqual(response_data['payment_processor'], 'dummy_with_url')
