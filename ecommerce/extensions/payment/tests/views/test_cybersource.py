""" Tests of the Payment Views. """
from __future__ import unicode_literals

import json

import ddt
import mock
from django.conf import settings
from django.core.urlresolvers import reverse
from freezegun import freeze_time
from oscar.apps.payment.exceptions import TransactionDeclined
from oscar.core.loading import get_class, get_model
from oscar.test import factories

from ecommerce.core.url_utils import get_lms_url
from ecommerce.extensions.payment.exceptions import InvalidBasketError, InvalidSignatureError
from ecommerce.extensions.payment.tests.mixins import CybersourceMixin, CybersourceNotificationTestsMixin
from ecommerce.extensions.payment.views.cybersource import CybersourceInterstitialView
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Selector = get_class('partner.strategy', 'Selector')

post_checkout = get_class('checkout.signals', 'post_checkout')


@ddt.ddt
class CybersourceSubmitViewTests(CybersourceMixin, TestCase):
    path = reverse('cybersource:submit')

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


@ddt.ddt
class CybersourceInterstitialViewTests(CybersourceNotificationTestsMixin, TestCase):
    """ Test interstitial view for Cybersource Payments. """
    path = reverse('cybersource:redirect')
    view = CybersourceInterstitialView

    def test_payment_declined(self):
        """
        Verify that the user is redirected to the basket summary page when their
        payment is declined.
        """
        # Basket merging clears lines on the old basket. We need to take a snapshot
        # of lines currently on this basket before it gets merged with a new basket.
        old_lines = list(self.basket.lines.all())

        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )

        with mock.patch.object(self.view, 'validate_notification', side_effect=TransactionDeclined):
            response = self.client.post(self.path, notification)

            self.assertRedirects(
                response,
                self.get_full_url(path=reverse('basket:summary')),
                status_code=302,
                fetch_redirect_response=False
            )

            new_basket = Basket.objects.get(status='Open')
            merged_basket_count = Basket.objects.filter(status='Merged').count()

            self.assertEqual(list(new_basket.lines.all()), old_lines)
            self.assertEqual(merged_basket_count, 1)

    @ddt.data(InvalidSignatureError, InvalidBasketError, Exception)
    def test_invalid_payment_error(self, error_class):
        """
        Verify that the view redirects to the payment error page when an error
        occurs while processing a payment notification.
        """
        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        with mock.patch.object(self.view, 'validate_notification', side_effect=error_class):
            response = self.client.post(self.path, notification)
            self.assertRedirects(response, self.get_full_url(reverse('payment_error')))

    def test_payment_error_context(self):
        response = self.client.get(reverse('payment_error'))
        self.assertDictContainsSubset(
            {
                'dashboard_url': get_lms_url(),
                'payment_support_email': self.site.siteconfiguration.payment_support_email
            },
            response.context
        )

    def test_successful_order(self):
        """ Verify the view redirects to the Receipt page when the Order has been successfully placed. """
        # The basket should not have an associated order if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        response = self.client.post(self.path, notification)
        self.assertTrue(Order.objects.filter(basket=self.basket).exists())
        self.assertEqual(response.status_code, 302)

    def test_order_creation_error(self):
        """ Verify the view redirects to the Payment error page when an error occurred during Order creation. """
        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        with mock.patch.object(self.view, 'create_order', side_effect=Exception):
            response = self.client.post(self.path, notification)
            self.assertRedirects(response, self.get_full_url(path=reverse('payment_error')), status_code=302)
