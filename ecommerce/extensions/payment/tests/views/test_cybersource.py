""" Tests of the Payment Views. """
from __future__ import absolute_import, unicode_literals

import itertools
import json

import ddt
import mock
import responses
from django.conf import settings
from django.contrib.auth import get_user
from django.test.client import RequestFactory
from django.urls import reverse
from freezegun import freeze_time
from oscar.apps.payment.exceptions import TransactionDeclined
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from testfixtures import LogCapture

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_SWITCH
from ecommerce.core.models import BusinessClient, User
from ecommerce.core.tests import toggle_switch
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.basket.constants import PURCHASER_BEHALF_ATTRIBUTE
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.exceptions import InvalidBasketError, InvalidSignatureError
from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.tests.mixins import CybersourceMixin, CybersourceNotificationTestsMixin
from ecommerce.extensions.payment.utils import SDNClient
from ecommerce.extensions.payment.views.cybersource import CybersourceInterstitialView
from ecommerce.extensions.test.factories import create_basket, create_order
from ecommerce.invoice.models import Invoice
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'

Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Product = get_model('catalogue', 'Product')
Selector = get_class('partner.strategy', 'Selector')
Source = get_model('payment', 'Source')

post_checkout = get_class('checkout.signals', 'post_checkout')


class LoginMixin:
    def setUp(self):
        super(LoginMixin, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)


@ddt.ddt
class CybersourceSubmitViewTests(CybersourceMixin, TestCase):
    path = reverse('cybersource:submit')
    CYBERSOURCE_VIEW_LOGGER_NAME = 'ecommerce.extensions.payment.views.cybersource'

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

    def assert_basket_retrieval_error(self, basket_id):
        error_msg = 'There was a problem retrieving your basket. Refresh the page to try again.'
        return self._assert_basket_error(basket_id, error_msg)

    def test_login_required(self):
        """ Verify the view redirects anonymous users to the login page. """
        self.client.logout()
        response = self.client.post(self.path)
        expected_url = '{base}?next={path}'.format(base=reverse(settings.LOGIN_URL),
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
        self.assertDictEqual(response.json(), expected)

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

    def test_sdn_check_match(self):
        """Verify the endpoint returns an sdn check failure if the sdn check finds a hit."""
        self.site.siteconfiguration.enable_sdn_check = True
        self.site.siteconfiguration.save()

        basket_id = self._create_valid_basket().id
        data = self._generate_data(basket_id)
        expected_response = {'error': 'There was an error submitting the basket', 'sdn_check_failure': {'hit_count': 1}}
        logger_name = self.CYBERSOURCE_VIEW_LOGGER_NAME

        with mock.patch.object(SDNClient, 'search', return_value={'total': 1}) as sdn_validator_mock:
            with mock.patch.object(User, 'deactivate_account', return_value=True):
                with LogCapture(logger_name) as cybersource_logger:
                    response = self.client.post(self.path, data)
                    self.assertTrue(sdn_validator_mock.called)
                    self.assertEqual(response.json(), expected_response)
                    self.assertEqual(response.status_code, 403)
                    cybersource_logger.check_present(
                        (
                            logger_name,
                            'INFO',
                            'SDNCheck function called for basket [{}]. It received 1 hit(s).'.format(basket_id)
                        ),
                    )
                    # Make sure user is logged out
                    self.assertEqual(get_user(self.client).is_authenticated, False)

    @freeze_time('2016-01-01')
    def test_valid_request(self):
        """ Verify the view returns the CyberSource parameters if the request is valid. """
        basket = self._create_valid_basket()
        data = self._generate_data(basket.id)
        response = self.client.post(self.path, data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], JSON)

        actual = response.json()['form_fields']
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

        errors = response.json()['field_errors']
        self.assertIn(field, errors)


class CybersourceSubmitAPIViewTests(CybersourceSubmitViewTests):
    path = reverse('cybersource:api_submit')

    def setUp(self):  # pylint: disable=useless-super-delegation
        super(CybersourceSubmitAPIViewTests, self).setUp()

    def test_login_required(self):
        """ Verify the view returns 401 for unauthenticated users. """
        self.client.logout()
        response = self.client.post(self.path)
        self.assertEqual(response.status_code, 401)

    @freeze_time('2016-01-01')
    def test_valid_request(self):
        """ Verify the view returns the CyberSource parameters if the request is valid. """
        super(CybersourceSubmitAPIViewTests, self).test_valid_request()


@ddt.ddt
class CybersourceInterstitialViewTests(CybersourceNotificationTestsMixin, TestCase):
    """ Test interstitial view for Cybersource Payments. """
    path = reverse('cybersource:redirect')
    view = CybersourceInterstitialView

    @ddt.data(
        ('12345678-1234-1234-1234-123456789abc', 1),
        (None, 0)
    )
    @ddt.unpack
    def test_payment_declined(self, bundle, bundle_attr_count):
        """
        Verify that the user is redirected to the basket summary page when their
        payment is declined.
        """
        # Basket merging clears lines on the old basket. We need to take a snapshot
        # of lines currently on this basket before it gets merged with a new basket.
        old_lines = list(self.basket.lines.all())
        if bundle:
            BasketAttribute.objects.update_or_create(
                basket=self.basket,
                attribute_type=BasketAttributeType.objects.get(name='bundle_identifier'),
                value_text=bundle
            )

        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
        )

        logger_name = self.CYBERSOURCE_VIEW_LOGGER_NAME
        with mock.patch.object(self.view, 'validate_notification', side_effect=TransactionDeclined):
            with LogCapture(logger_name) as cybersource_logger:
                response = self.client.post(self.path, notification)

                self.assertRedirects(
                    response,
                    self.get_full_url(path=reverse('basket:summary')),
                    status_code=302,
                    fetch_redirect_response=False
                )

                new_basket = Basket.objects.get(status='Open')
                merged_basket_count = Basket.objects.filter(status='Merged').count()
                new_basket_bundle_count = BasketAttribute.objects.filter(
                    basket=new_basket,
                    attribute_type=BasketAttributeType.objects.get(name='bundle_identifier')
                ).count()

                self.assertEqual(list(new_basket.lines.all()), old_lines)
                self.assertEqual(merged_basket_count, 1)
                self.assertEqual(new_basket_bundle_count, bundle_attr_count)

                log_msg = 'Created new basket [{}] from old basket [{}] for declined transaction with bundle [{}].'
                cybersource_logger.check_present(
                    (
                        logger_name,
                        'INFO',
                        log_msg.format(
                            new_basket.id,
                            self.basket.id,
                            bundle
                        )
                    ),
                )

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
        course.create_or_update_seat('verified', True, 50, create_enrollment_code=True)
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
        request_data.update({PURCHASER_BEHALF_ATTRIBUTE: "False"})
        # Manually add organization and purchaser attributes on the basket for testing
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

    def test_duplicate_order_attempt_logging(self):
        """
        Verify that attempts at creation of a duplicate order are logged correctly
        """
        prior_order = create_order()
        dummy_request = RequestFactory(SERVER_NAME='testserver.fake').get('')
        dummy_mixin = EdxOrderPlacementMixin()
        dummy_mixin.payment_processor = Cybersource(self.site)

        with LogCapture(self.DUPLICATE_ORDER_LOGGER_NAME) as lc:
            with self.assertRaises(ValueError):
                dummy_mixin.create_order(dummy_request, prior_order.basket, None)
                lc.check(
                    (
                        self.DUPLICATE_ORDER_LOGGER_NAME,
                        'ERROR',
                        self.get_duplicate_order_error_message(payment_processor='Cybersource', order=prior_order)
                    ),
                )

    def test_order_creation_after_duplicate_reference_number_error(self):
        """ Verify view creates the order if there is no existing order in case of DuplicateReferenceNumber """
        self.assertFalse(Order.objects.filter(basket=self.basket).exists())
        notification = self.generate_notification(
            self.basket,
            billing_address=self.billing_address,
            decision='error',
            reason_code='104',
        )
        response = self.client.post(self.path, notification)
        self.assertTrue(Order.objects.filter(basket=self.basket).exists())
        self.assertEqual(response.status_code, 302)


@ddt.ddt
class ApplePayStartSessionViewTests(LoginMixin, TestCase):
    url = reverse('cybersource:apple_pay:start_session')
    payment_microfrontend_domain = 'payment-mfe.org'

    def _call_to_apple_pay_and_assert_response(self, status, body, request_from_mfe=False, expected_mfe=False):
        url = 'https://apple-pay-gateway.apple.com/paymentservices/startSession'
        body = json.dumps(body)
        responses.add(responses.POST, url, body=body, status=status, content_type=JSON)

        post_data = {'url': url}
        if request_from_mfe:
            post_data.update({'is_payment_microfrontend': True})

        response = self.client.post(self.url, json.dumps(post_data), JSON)
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.content.decode('utf-8'), body)

        expected_domain_name = self.payment_microfrontend_domain if expected_mfe else 'testserver.fake'
        self.assertEqual(
            json.loads(responses.calls[0].request.body.decode('utf-8'))['domainName'],
            expected_domain_name,
        )

    @ddt.data(
        (200, {'foo': 'bar'}),
        (500, {'error': 'Failure!'})
    )
    @ddt.unpack
    @responses.activate
    def test_post(self, status, body):
        """ The view should POST to the given URL and return the response. """
        self._call_to_apple_pay_and_assert_response(status, body)

    @responses.activate
    @ddt.data(*itertools.product((True, False), (True, False)))
    @ddt.unpack
    def test_with_microfrontend(self, request_from_mfe, enable_microfrontend):
        self.site.siteconfiguration.enable_microfrontend_for_basket_page = enable_microfrontend
        self.site.siteconfiguration.payment_microfrontend_url = 'http://{}'.format(self.payment_microfrontend_domain)
        self.site.siteconfiguration.save()

        self._call_to_apple_pay_and_assert_response(
            200,
            {'foo': 'bar'},
            request_from_mfe,
            request_from_mfe and enable_microfrontend,
        )

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
