import json

import stripe
from ddt import ddt, file_data
from django.conf import settings
from django.urls import reverse
from mock import mock
from oscar.core.loading import get_class, get_model
from rest_framework import status

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.constants import STRIPE_CARD_TYPE_MAP
from ecommerce.extensions.payment.processors.stripe import Stripe
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.extensions.test.factories import create_basket
from ecommerce.tests.testcases import TestCase

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Country = get_model('address', 'Country')
Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
Selector = get_class('partner.strategy', 'Selector')
Source = get_model('payment', 'Source')
Product = get_model('catalogue', 'Product')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

STRIPE_TEST_FIXTURE_PATH = 'ecommerce/extensions/payment/tests/views/fixtures/test_stripe_test_payment_flow.json'


@ddt
class StripeCheckoutViewTests(PaymentEventsMixin, TestCase):
    path = reverse('stripe:submit')

    def setUp(self):
        super(StripeCheckoutViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        self.site.siteconfiguration.client_side_payment_processor = 'stripe'
        self.site.siteconfiguration.save()
        Country.objects.create(iso_3166_1_a2='US', name='US')
        self.mock_enrollment_api_resp = mock.Mock()
        self.mock_enrollment_api_resp.status_code = status.HTTP_200_OK

        self.stripe_checkout_url = reverse('stripe:checkout')
        self.capture_context_url = reverse('bff:payment:v0:capture_context')

    def payment_flow_with_mocked_stripe_calls(
            self,
            url,
            data,
            create_side_effect=None,
            retrieve_side_effect=None,
            confirm_side_effect=None,
            modify_side_effect=None):
        """
        Helper function to mock all stripe calls with successful responses.

        Useful for when you want to mock something else without a wall
        of context managers in your test.
        """
        # Requires us to run tests from repo root directory. Too fragile?
        with open(STRIPE_TEST_FIXTURE_PATH, 'r') as fixtures:  # pylint: disable=unspecified-encoding
            fixture_data = json.load(fixtures)['happy_path']

        # hit capture_context first
        with mock.patch('stripe.PaymentIntent.create') as mock_create:
            if create_side_effect is not None:
                mock_create.side_effect = create_side_effect
            else:
                mock_create.side_effect = [fixture_data['create_resp']]
            self.client.get(self.capture_context_url)

        # now hit POST endpoint
        with mock.patch('stripe.PaymentIntent.retrieve') as mock_retrieve:
            if retrieve_side_effect is not None:
                mock_retrieve.side_effect = retrieve_side_effect
            else:
                mock_retrieve.side_effect = [fixture_data['retrieve_addr_resp']]

            with mock.patch(
                'ecommerce.extensions.fulfillment.modules.EnrollmentFulfillmentModule._post_to_enrollment_api'
            ) as mock_api_resp:
                mock_api_resp.return_value = self.mock_enrollment_api_resp

                with mock.patch('stripe.PaymentIntent.confirm') as mock_confirm:
                    if confirm_side_effect is not None:
                        mock_confirm.side_effect = confirm_side_effect
                    else:
                        mock_confirm.side_effect = [fixture_data['confirm_resp']]
                    with mock.patch('stripe.PaymentIntent.modify') as mock_modify:
                        if modify_side_effect is not None:
                            mock_modify.side_effect = modify_side_effect
                        else:
                            mock_modify.side_effect = [fixture_data['modify_resp']]
                        # make your call
                        return self.client.post(
                            url,
                            data=data
                        )

    def assert_successful_order_response(self, response, order_number):
        assert response.status_code == 201
        receipt_url = get_receipt_page_url(
            self.request,
            self.site_configuration,
            order_number,
            disable_back_button=True
        )
        assert response.json() == {'url': receipt_url}

    def assert_order_created(self, basket, billing_address, card_type, label):
        order = Order.objects.get(number=basket.order_number, total_incl_tax=basket.total_incl_tax)
        total = order.total_incl_tax
        order.payment_events.get(event_type__code='paid', amount=total)
        Source.objects.get(
            source_type__name=Stripe.NAME,
            currency=order.currency,
            amount_allocated=total,
            amount_debited=total,
            card_type=STRIPE_CARD_TYPE_MAP[card_type],
            label=label
        )
        PaymentEvent.objects.get(
            event_type__name=PaymentEventTypeName.PAID,
            amount=total,
            processor_name=Stripe.NAME
        )
        assert order.billing_address == billing_address

    def create_basket(self, product_class=None):
        basket = create_basket(owner=self.user, site=self.site, product_class=product_class)
        basket.strategy = Selector().strategy()
        basket.thaw()
        basket.flush()
        course = CourseFactory()
        seat = course.create_or_update_seat('credit', False, 100, 'credit_provider_id', None, 2)
        basket.add_product(seat, 1)
        return basket

    def test_login_required(self):
        self.client.logout()
        response = self.client.post(self.path)
        expected_url = '{base}?next={path}'.format(base=reverse(settings.LOGIN_URL), path=self.path)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @file_data('fixtures/test_stripe_test_payment_flow.json')
    def test_payment_flow(
            self,
            confirm_resp,
            create_resp,
            modify_resp,
            refund_resp,  # pylint: disable=unused-argument
            retrieve_addr_resp):
        """
        Verify that the stripe payment flow, hitting capture-context and
        stripe-checkout urls, results in a basket associated with the correct
        stripe payment_intent_id.

        Args:
            confirm_resp: Response for confirm call on payment purchase
            create_resp: Response for create call when capturing context
            modify_resp: Response for modify call before confirming response
            retrieve_addr_resp: Response for retrieve call that should be made when getting billing address
            confirm_resp: Response for confirm call that should be made when handling processor response
        """
        basket = self.create_basket(product_class=SEAT_PRODUCT_CLASS_NAME)
        idempotency_key = f'basket_pi_create_v1_{basket.order_number}'

        # need to call capture-context endpoint before we call do GET to the stripe checkout view
        # so that the PaymentProcessorResponse is already created
        with mock.patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.return_value = create_resp
            self.client.get(self.capture_context_url)
            mock_create.assert_called_once()
            assert mock_create.call_args.kwargs['idempotency_key'] == idempotency_key

        with mock.patch('stripe.PaymentIntent.retrieve') as mock_retrieve:
            mock_retrieve.return_value = retrieve_addr_resp

            with mock.patch(
                'ecommerce.extensions.fulfillment.modules.EnrollmentFulfillmentModule._post_to_enrollment_api'
            ) as mock_api_resp:
                mock_api_resp.return_value = self.mock_enrollment_api_resp

                with mock.patch('stripe.PaymentIntent.confirm') as mock_confirm:
                    mock_confirm.return_value = confirm_resp
                    with mock.patch('stripe.PaymentIntent.modify') as mock_modify:
                        mock_modify.return_value = modify_resp
                        self.client.post(
                            self.stripe_checkout_url,
                            data={
                                'payment_intent_id': 'pi_3LsftNIadiFyUl1x2TWxaADZ',
                                'skus': basket.lines.first().stockrecord.partner_sku,
                            },
                        )
                assert mock_retrieve.call_count == 1
                assert mock_modify.call_count == 1
                assert mock_confirm.call_count == 1

        # Verify BillingAddress was set correctly
        basket.refresh_from_db()
        order = basket.order_set.first()
        assert str(order.billing_address) == "Test User, 123 Test St, Sample, MA, 12345"

        # Verify there is 1 and only 1 Basket Attribute with the payment_intent_id
        # associated with our basket.
        assert BasketAttribute.objects.filter(
            value_text='pi_3LsftNIadiFyUl1x2TWxaADZ',
            basket=basket,
        ).count() == 1

        pprs = PaymentProcessorResponse.objects.filter(
            transaction_id="pi_3LsftNIadiFyUl1x2TWxaADZ"
        )
        # created when andle_processor_response is successful
        assert pprs.count() == 1

    def test_capture_context_basket_price_change(self):
        """
        Verify that existing payment intent is retrieved,
        and that we do not error with an IdempotencyError in this case: capture
        context is called to generate stripe elements, but then user backs out from
        payment page, and tries to check out with a different things in the basket.
        """
        basket = self.create_basket(product_class=SEAT_PRODUCT_CLASS_NAME)
        idempotency_key = f'basket_pi_create_v1_{basket.order_number}'

        with mock.patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.return_value = {
                'id': 'pi_3LsftNIadiFyUl1x2TWxaADZ',
                'client_secret': 'pi_3LsftNIadiFyUl1x2TWxaADZ_secret_VxRx7Y1skyp0jKtq7Gdu80Xnh',
            }
            self.client.get(self.capture_context_url)
            mock_create.assert_called_once()
            assert mock_create.call_args.kwargs['idempotency_key'] == idempotency_key

        # Verify there is 1 and only 1 Basket Attribute with the payment_intent_id
        # associated with our basket.
        assert BasketAttribute.objects.filter(
            value_text='pi_3LsftNIadiFyUl1x2TWxaADZ',
            basket=basket,
        ).count() == 1

        # Change the basket price
        basket.flush()
        course = CourseFactory()
        seat = course.create_or_update_seat('credit', False, 99, 'credit_provider_id', None, 2)
        basket.add_product(seat, 1)
        basket.save()

        with mock.patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.side_effect = stripe.error.IdempotencyError

            with mock.patch('stripe.PaymentIntent.retrieve') as mock_retrieve:
                mock_retrieve.return_value = {
                    'id': 'pi_3LsftNIadiFyUl1x2TWxaADZ',
                    'client_secret': 'pi_3LsftNIadiFyUl1x2TWxaADZ_secret_VxRx7Y1skyp0jKtq7Gdu80Xnh',
                }
                self.client.get(self.capture_context_url)
                mock_retrieve.assert_called_once()
                assert mock_retrieve.call_args.kwargs['id'] == 'pi_3LsftNIadiFyUl1x2TWxaADZ'

    def test_capture_context_empty_basket(self):
        basket = create_basket(owner=self.user, site=self.site)
        basket.flush()

        with mock.patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.return_value = {
                'id': '',
                'client_secret': '',
            }

            self.assertTrue(basket.is_empty)
            response = self.client.get(self.capture_context_url)

            mock_create.assert_not_called()
            self.assertDictEqual(response.json(), {
                'capture_context': {
                    'key_id': mock_create.return_value['client_secret'],
                    'order_id': basket.order_number,
                }
            })
            self.assertEqual(response.status_code, 200)

    def test_payment_error_no_basket(self):
        """
        Verify view redirects to error page if no basket exists for payment_intent_id.
        """
        # Post without actually making a basket
        response = self.client.post(
            self.stripe_checkout_url,
            data={
                'payment_intent_id': 'pi_3LsftNIadiFyUl1x2TWxaADZ',
                'skus': '',
            },
        )
        assert response.status_code == 302
        assert response.url == "http://testserver.fake/checkout/error/"

    def test_payment_error_sku_mismatch(self):
        """
        Verify a sku mismatch between basket and request logs warning.
        """
        basket = self.create_basket(product_class=SEAT_PRODUCT_CLASS_NAME)

        with self.assertLogs(level='WARNING') as log:
            response = self.payment_flow_with_mocked_stripe_calls(
                self.stripe_checkout_url,
                {
                    'payment_intent_id': 'pi_3LsftNIadiFyUl1x2TWxaADZ',
                    'skus': 'totally_the_wrong_sku',
                },
            )
            assert response.json() == {'sku_error': True}
            assert response.status_code == 400
            expected_log = (
                "WARNING:ecommerce.extensions.payment.views.stripe:"
                "Basket [%s] SKU mismatch! request_skus "
                "[{'totally_the_wrong_sku'}] and basket_skus [{'%s'}]."
                % (basket.id, basket.lines.first().stockrecord.partner_sku)
            )
            actual_log = log.output[0]
            assert actual_log == expected_log

    def test_payment_check_sdn_returns_hits(self):
        """
        Verify positive SDN hits returns correct error JSON.
        """
        basket = self.create_basket(product_class=SEAT_PRODUCT_CLASS_NAME)

        with mock.patch('ecommerce.extensions.payment.views.stripe.checkSDN') as mock_sdn_check:
            mock_sdn_check.return_value = 1
            response = self.payment_flow_with_mocked_stripe_calls(
                self.stripe_checkout_url,
                {
                    'payment_intent_id': 'pi_3LsftNIadiFyUl1x2TWxaADZ',
                    'skus': basket.lines.first().stockrecord.partner_sku,
                },
            )
            assert response.status_code == 400
            assert response.json() == {'sdn_check_failure': {'hit_count': 1}}

    def test_handle_payment_fails_with_carderror(self):
        """
        Verify handle payment failing with CardError returns correct error JSON.
        """
        basket = self.create_basket(product_class=SEAT_PRODUCT_CLASS_NAME)

        response = self.payment_flow_with_mocked_stripe_calls(
            self.stripe_checkout_url,
            {
                'payment_intent_id': 'pi_3LsftNIadiFyUl1x2TWxaADZ',
                'skus': basket.lines.first().stockrecord.partner_sku,
            },
            confirm_side_effect=stripe.error.CardError('Oops!', {}, 'card_declined'),
        )
        assert response.status_code == 400
        assert response.json() == {'error_code': 'card_declined', 'user_message': 'Oops!'}

    def test_handle_payment_fails_with_unexpected_error(self):
        """
        Verify handle payment failing with unexpected error returns correct JSON response.
        """
        basket = self.create_basket(product_class=SEAT_PRODUCT_CLASS_NAME)

        path = 'ecommerce.extensions.payment.views.stripe.StripeCheckoutView.handle_payment'
        with mock.patch(path) as mock_handle_payment:
            mock_handle_payment.side_effect = ZeroDivisionError
            response = self.payment_flow_with_mocked_stripe_calls(
                self.stripe_checkout_url,
                {
                    'payment_intent_id': 'pi_3LsftNIadiFyUl1x2TWxaADZ',
                    'skus': basket.lines.first().stockrecord.partner_sku,
                },
            )
            assert response.status_code == 400
            assert response.json() == {}

    def test_create_billing_address_fails(self):
        """
        Verify order is not successful if billing address objects fails
        to be created.
        """
        basket = self.create_basket(product_class=SEAT_PRODUCT_CLASS_NAME)

        path = 'ecommerce.extensions.payment.views.stripe.StripeCheckoutView.create_billing_address'
        with mock.patch(path) as mock_billing_create:
            mock_billing_create.side_effect = Exception
            response = self.payment_flow_with_mocked_stripe_calls(
                self.stripe_checkout_url,
                {
                    'payment_intent_id': 'pi_3LsftNIadiFyUl1x2TWxaADZ',
                    'skus': basket.lines.first().stockrecord.partner_sku,
                },
            )
            assert response.status_code == 400
            assert response.json() == {}

        basket.refresh_from_db()
        assert not basket.order_set.exists()

    # def test_successful_payment_for_bulk_purchase(self):
    #     """
    #     Verify that when a Order has been successfully placed for bulk
    #     purchase then that order is linked to the provided business client.
    #     """
    #     toggle_switch(ENROLLMENT_CODE_SWITCH, True)

    #     course = CourseFactory(partner=self.partner)
    #     course.create_or_update_seat('verified', True, 50, create_enrollment_code=True)
    #     basket = create_basket(owner=self.user, site=self.site)
    #     enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
    #     basket.add_product(enrollment_code, quantity=1)
    #     basket.strategy = Selector().strategy()

    #     data = self.generate_form_data(basket.id)
    #     data.update({'organization': 'Dummy Business Client'})
    #     data.update({PURCHASER_BEHALF_ATTRIBUTE: 'False'})

    #     # Manually add organization attribute on the basket for testing
    #     basket_add_organization_attribute(basket, data)

    #     card_type = 'visa'
    #     label = '4242'
    #     payment_intent = stripe.PaymentIntent.construct_from({
    #         'id': 'pi_testtesttest',
    #         'source': {
    #             'brand': card_type,
    #             'last4': label,
    #         },
    #     }, 'fake-key')

    #     billing_address = BillingAddressFactory()
    #     with mock.patch.object(Stripe, 'get_address_from_token') as address_mock:
    #         address_mock.return_value = billing_address

    #         with mock.patch.object(stripe.PaymentIntent, 'create') as pi_mock:
    #             pi_mock.return_value = payment_intent
    #             response = self.client.post(self.path, data)

    #         address_mock.assert_called_once_with(data['payment_intent_id'])

    #     self.assert_successful_order_response(response, basket.order_number)
    #     self.assert_order_created(basket, billing_address, card_type, label)

    #     # Now verify that a new business client has been created and current
    #     # order is now linked with that client through Invoice model.
    #     order = Order.objects.filter(basket=basket).first()
    #     business_client = BusinessClient.objects.get(name=data['organization'])
    #     assert Invoice.objects.get(order=order).business_client == business_client
