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
                            data={'payment_intent_id': 'pi_3LsftNIadiFyUl1x2TWxaADZ'},
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

    # def test_payment_error(self):
    #     basket = self.create_basket()
    #     data = self.generate_form_data(basket.id)

    #     with mock.patch.object(Stripe, 'get_address_from_token', mock.Mock(return_value=BillingAddressFactory())):
    #         with mock.patch.object(Stripe, 'handle_processor_response', mock.Mock(side_effect=Exception)):
    #             response = self.client.post(self.path, data)

    #     assert response.status_code == 400
    #     assert response.content.decode('utf-8') == '{}'

    # def test_billing_address_error(self):
    #     basket = self.create_basket()
    #     data = self.generate_form_data(basket.id)
    #     card_type = 'visa'
    #     label = '4242'
    #     payment_intent = stripe.PaymentIntent.construct_from({
    #         'id': 'pi_testtesttest',
    #         'source': {
    #             'brand': card_type,
    #             'last4': label,
    #         },
    #     }, 'fake-key')

    #     with mock.patch.object(Stripe, 'get_address_from_token') as address_mock:
    #         address_mock.side_effect = Exception

    #         with mock.patch.object(stripe.PaymentIntent, 'create') as pi_mock:
    #             pi_mock.return_value = payment_intent
    #             response = self.client.post(self.path, data)

    #         address_mock.assert_called_once_with(data['payment_intent_id'])

    #     self.assert_successful_order_response(response, basket.order_number)
    #     self.assert_order_created(basket, None, card_type, label)

    # def test_successful_payment(self):
    #     basket = self.create_basket()
    #     data = self.generate_form_data(basket.id)
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
