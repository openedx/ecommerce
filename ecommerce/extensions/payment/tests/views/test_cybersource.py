""" Tests of the Payment Views. """
from __future__ import unicode_literals

import datetime
import json

import ddt
import mock
import responses
from django.conf import settings
from django.urls import reverse
from django.utils.timezone import now
from freezegun import freeze_time
from oscar.apps.payment.exceptions import TransactionDeclined
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from waffle.testutils import override_switch

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_SWITCH
from ecommerce.core.models import BusinessClient
from ecommerce.core.tests import toggle_switch
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.constants import VOUCHER_VALIDATION_BEFORE_PAYMENT
from ecommerce.extensions.payment.exceptions import InvalidBasketError, InvalidSignatureError
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.tests.mixins import CybersourceMixin, CybersourceNotificationTestsMixin
from ecommerce.extensions.payment.views.cybersource import CybersourceInterstitialView
from ecommerce.extensions.test.factories import create_basket, prepare_voucher
from ecommerce.invoice.models import Invoice
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Product = get_model('catalogue', 'Product')
Selector = get_class('partner.strategy', 'Selector')
Source = get_model('payment', 'Source')
Voucher = get_model('voucher', 'Voucher')

post_checkout = get_class('checkout.signals', 'post_checkout')


class LoginMixin(object):
    def setUp(self):
        super(LoginMixin, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)


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
        basket = create_basket(owner=self.user, site=self.site)
        basket.strategy = Selector().strategy()
        basket.thaw()
        return basket

    def _prepare_basket_for_voucher_validation_tests(self, voucher_start_date, voucher_end_date):
        """ Prepares basket for voucher validation """
        basket = Basket.objects.create(site=self.site, owner=self.user)
        voucher, product = prepare_voucher(start_datetime=voucher_start_date, end_datetime=voucher_end_date)
        basket.strategy = Selector().strategy()
        basket.add_product(product)
        basket.vouchers.add(voucher)
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
        expected = {
            'error': error_msg,
            'field_errors': {'basket': error_msg}
        }
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
        error_msg = 'There was a problem retrieving your basket. Refresh the page to try again.'
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

    @override_switch(VOUCHER_VALIDATION_BEFORE_PAYMENT, active=True)
    @ddt.data(
        (now() - datetime.timedelta(days=3), 400),
        (now() + datetime.timedelta(days=3), 200))
    @ddt.unpack
    def test_submit_view_fails_for_invalid_voucher(self, voucher_end_time, status_code):
        """ Verify SubmitPaymentView fails if basket invalid voucher"""
        # Create Basket and payment data
        voucher_start_time = now() - datetime.timedelta(days=5)
        basket = self._prepare_basket_for_voucher_validation_tests(voucher_start_time, voucher_end_time)

        data = self._generate_data(basket.id)
        response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, status_code)
        self.assertEqual(response['content-type'], JSON)

    @override_switch(VOUCHER_VALIDATION_BEFORE_PAYMENT, active=True)
    @mock.patch(
        'ecommerce.extensions.voucher.models.Voucher.is_available_to_user',
        return_value=(False, None)
    )
    def test_submit_view_fails_if_voucher_not_available(self, mock_is_available_to_user):
        """ Verify SubmitPaymentView fails if basket voucher not available to student"""
        # Create Basket and payment data
        voucher_start_time = now() - datetime.timedelta(days=1)
        voucher_end_time = now() + datetime.timedelta(days=3)
        basket = self._prepare_basket_for_voucher_validation_tests(voucher_start_time, voucher_end_time)

        data = self._generate_data(basket.id)
        response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response['content-type'], JSON)
        self.assertEqual(mock_is_available_to_user.call_count, 3)

    @override_switch(VOUCHER_VALIDATION_BEFORE_PAYMENT, active=False)
    def test_successful_submit_view_with_voucher_switch_disabled(self):
        """
        Temporary test to confirm the problem with SubmitPaymentView
        Accepting an invalid voucher when the waffle switch is False.
        This will be cleaned up in LEARNER-5719.
        """
        voucher_start_time = now() - datetime.timedelta(days=5)
        voucher_end_time = now() - datetime.timedelta(days=3)
        basket = self._prepare_basket_for_voucher_validation_tests(voucher_start_time, voucher_end_time)

        data = self._generate_data(basket.id)
        response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], JSON)


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

    def test_successful_order_for_bulk_purchase(self):
        """
        Verify the view redirects to the Receipt page when the Order has been
        successfully placed for bulk purchase and also that the order is linked
        to the provided business client.
        """
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)

        course = CourseFactory()
        course.create_or_update_seat('verified', True, 50, self.partner, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        self.basket = create_basket(owner=self.user, site=self.site)
        self.basket.add_product(enrollment_code, quantity=1)

        # The basket should not have an associated order if no payment was made.
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())

        request_data = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        request_data.update({'organization': 'Dummy Business Client'})
        # Manually add organization attribute on the basket for testing
        basket_add_organization_attribute(self.basket, request_data)

        response = self.client.post(self.path, request_data)
        self.assertTrue(Order.objects.filter(basket=self.basket).exists())
        self.assertEqual(response.status_code, 302)

        # Now verify that a new business client has been created and current
        # order is now linked with that client through Invoice model.
        order = Order.objects.filter(basket=self.basket).first()
        business_client = BusinessClient.objects.get(name=request_data['organization'])
        assert Invoice.objects.get(order=order).business_client == business_client

    def test_order_creation_error(self):
        """ Verify the view redirects to the Payment error page when an error occurred during Order creation. """
        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )
        with mock.patch.object(self.view, 'create_order', side_effect=Exception):
            response = self.client.post(self.path, notification)
            self.assertRedirects(response, self.get_full_url(path=reverse('payment_error')), status_code=302)


@ddt.ddt
class ApplePayStartSessionViewTests(LoginMixin, TestCase):
    url = reverse('cybersource:apple_pay:start_session')

    @ddt.data(
        (200, {'foo': 'bar'}),
        (500, {'error': 'Failure!'})
    )
    @ddt.unpack
    @responses.activate
    def test_post(self, status, body):
        """ The view should POST to the given URL and return the response. """
        url = 'https://apple-pay-gateway.apple.com/paymentservices/startSession'
        body = json.dumps(body)
        responses.add(responses.POST, url, body=body, status=status, content_type=JSON)

        response = self.client.post(self.url, json.dumps({'url': url}), JSON)
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.content, body)

    def test_post_without_url(self):
        """ The view should return HTTP 400 if no url parameter is posted. """
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'error': 'url is required'})


@ddt.ddt
class CybersourceApplePayAuthorizationViewTests(LoginMixin, CybersourceMixin, TestCase):
    url = reverse('cybersource:apple_pay:authorize')

    def generate_post_data(self):
        address = factories.BillingAddressFactory()

        return {
            'billingContact': {
                'addressLines': [
                    address.line1,
                    address.line1
                ],
                'administrativeArea': address.state,
                'country': address.country.printable_name,
                'countryCode': address.country.iso_3166_1_a2,
                'familyName': self.user.last_name,
                'givenName': self.user.first_name,
                'locality': address.line4,
                'postalCode': address.postcode,
            },
            'shippingContact': {
                'emailAddress': self.user.email,
                'familyName': self.user.last_name,
                'givenName': self.user.first_name,
            },
            'token': {
                'paymentData': {
                    'version': 'EC_v1',
                    'data': 'fake-data',
                    'signature': 'fake-signature',
                    'header': {
                        'ephemeralPublicKey': 'fake-key',
                        'publicKeyHash': 'fake-hash',
                        'transactionId': 'abc123'
                    }
                },
                'paymentMethod': {
                    'displayName': 'AmEx 1086',
                    'network': 'AmEx',
                    'type': 'credit'
                },
                'transactionIdentifier': 'DEADBEEF'
            }
        }

    @responses.activate
    def test_post(self):
        """ The view should authorize and settle payment at CyberSource, and create an order. """
        data = self.generate_post_data()
        basket = create_basket(owner=self.user, site=self.site)
        basket.strategy = Selector().strategy()

        self.mock_cybersource_wsdl()
        self.mock_authorization_response(accepted=True)
        response = self.client.post(self.url, json.dumps(data), JSON)

        self.assertEqual(response.status_code, 201)
        PaymentProcessorResponse.objects.get(basket=basket)

        order = Order.objects.all().first()
        total = order.total_incl_tax
        self.assertEqual(response.data, OrderSerializer(order, context={'request': self.request}).data)
        order.payment_events.get(event_type__code='paid', amount=total)
        Source.objects.get(
            source_type__name=Cybersource.NAME, currency=order.currency, amount_allocated=total, amount_debited=total,
            label='Apple Pay')
        PaymentEvent.objects.get(event_type__name=PaymentEventTypeName.PAID, amount=total,
                                 processor_name=Cybersource.NAME)

    @responses.activate
    def test_post_with_rejected_payment(self):
        """ The view should return an error if CyberSource rejects payment. """
        data = self.generate_post_data()
        self.mock_cybersource_wsdl()
        self.mock_authorization_response(accepted=False)
        response = self.client.post(self.url, json.dumps(data), JSON)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data, {'error': 'payment_failed'})

    def test_post_with_invalid_billing_address(self):
        """ The view should return an error if the billing address is invalid. """
        data = self.generate_post_data()
        data['billingContact'] = {}
        response = self.client.post(self.url, json.dumps(data), JSON)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'error': 'billing_address_invalid'})

    def test_post_with_invalid_country(self):
        """ The view should log a warning if the country code is invalid. """
        data = self.generate_post_data()
        country_code = 'FAKE'
        data['billingContact']['countryCode'] = country_code

        with mock.patch('ecommerce.extensions.payment.views.cybersource.logger.warning') as mock_logger:
            response = self.client.post(self.url, json.dumps(data), JSON)
            mock_logger.assert_called_once_with('Country matching code [%s] does not exist.', country_code)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'error': 'billing_address_invalid'})

    def test_post_without_payment_token(self):
        """ The view should return an error if no payment token is provided. """
        data = self.generate_post_data()
        data['token'] = {}
        response = self.client.post(self.url, json.dumps(data), JSON)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {'error': 'token_missing'})
