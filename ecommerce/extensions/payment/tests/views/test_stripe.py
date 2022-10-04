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

    def test_payment_flow(self):
        """
        Verify that the stripe payment flow, hitting capture-context and
        stripe-checkout urls, results in a basket associated with the correct
        stripe payment_intent_id.
        """
        basket = self.create_basket(product_class=SEAT_PRODUCT_CLASS_NAME)
        idempotency_key = f'basket_pi_create_v1_{basket.order_number}'

        # need to call capture-context endpoint before we call do GET to the stripe checkout view
        # so that the PaymentProcessorResponse is already created
        with mock.patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.return_value = {
                'id': 'pi_testtesttest',
                'client_secret': 'a_client_secret',
            }
            self.client.get(self.capture_context_url)
            mock_create.assert_called_once()
            assert mock_create.call_args.kwargs['idempotency_key'] == idempotency_key

        response_dict = {
            'status': 'requires_payment_method',
            'charges': {
                'data': [{
                    'payment_method_details': {
                        'card': {
                            'last4': '6789',
                            'brand': 'credit_card_brand',
                        }
                    },
                    'billing_details': {
                        'address': {
                            'line1': '123 Town Road',
                            'line2': '',
                            'city': 'Townsville',
                            'postal_code': '02138',
                            'state': 'MA',
                            'country': 'US',
                        },
                        'email': 'test@example.com',
                        'name': 'John Doe',
                        'phone': None,
                    },
                }]
            },
        }
        # Response for retrieve call that should be made when getting billing address
        retrieve_resp = dict(response_dict)
        # Response for confim call that shouls be made when handling processor response
        confirm_resp = dict(response_dict)
        confirm_resp['status'] = 'succeeded'

        with mock.patch('stripe.PaymentIntent.retrieve') as mock_retrieve:
            mock_retrieve.return_value = retrieve_resp

            with mock.patch(
                'ecommerce.extensions.fulfillment.modules.EnrollmentFulfillmentModule._post_to_enrollment_api'
            ) as mock_api_resp:
                mock_api_resp.return_value = self.mock_enrollment_api_resp

                with mock.patch('stripe.PaymentIntent.confirm') as mock_confirm:
                    mock_confirm.return_value = confirm_resp
                    self.client.get(
                        self.stripe_checkout_url,
                        {'payment_intent': 'pi_testtesttest'},
                    )
                assert mock_retrieve.call_count == 1
                assert mock_confirm.call_count == 1

        # Verify BillingAddress was set correctly
        basket.refresh_from_db()
        order = basket.order_set.first()
        assert str(order.billing_address) == "John Doe, 123 Town Road, Townsville, MA, 02138"

        # Verify there is 1 and only 1 Basket Attribute with the payment_intent_id
        # associated with our basket.
        assert BasketAttribute.objects.filter(
            value_text='pi_testtesttest',
            basket=basket,
        ).count() == 1

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
