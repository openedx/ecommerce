

import stripe
from django.conf import settings
from django.urls import reverse
from mock import mock
from oscar.core.loading import get_class, get_model
from oscar.test.factories import BillingAddressFactory

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_SWITCH
from ecommerce.core.models import BusinessClient
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.basket.constants import PURCHASER_BEHALF_ATTRIBUTE
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.constants import STRIPE_CARD_TYPE_MAP
from ecommerce.extensions.payment.processors.stripe import Stripe
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.extensions.test.factories import create_basket
from ecommerce.invoice.models import Invoice
from ecommerce.tests.testcases import TestCase

Country = get_model('address', 'Country')
Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
Selector = get_class('partner.strategy', 'Selector')
Source = get_model('payment', 'Source')
Product = get_model('catalogue', 'Product')


class StripeSubmitViewTests(PaymentEventsMixin, TestCase):
    path = reverse('stripe:submit')

    def setUp(self):
        super(StripeSubmitViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def assert_successful_order_response(self, response, order_number):
        assert response.status_code == 201
        receipt_url = get_receipt_page_url(
            self.site_configuration,
            order_number,
            disable_back_button=True,
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

    def generate_form_data(self, basket_id):
        return {
            'stripe_token': 'st_abc123',
            'basket': basket_id,
        }

    def create_basket(self):
        basket = create_basket(owner=self.user, site=self.site)
        basket.strategy = Selector().strategy()
        basket.thaw()
        return basket

    def test_login_required(self):
        self.client.logout()
        response = self.client.post(self.path)
        expected_url = '{base}?next={path}'.format(base=reverse(settings.LOGIN_URL), path=self.path)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_payment_error(self):
        basket = self.create_basket()
        data = self.generate_form_data(basket.id)

        with mock.patch.object(Stripe, 'get_address_from_token', mock.Mock(return_value=BillingAddressFactory())):
            with mock.patch.object(Stripe, 'handle_processor_response', mock.Mock(side_effect=Exception)):
                response = self.client.post(self.path, data)

        assert response.status_code == 400
        assert response.content.decode('utf-8') == '{}'

    def test_billing_address_error(self):
        basket = self.create_basket()
        data = self.generate_form_data(basket.id)
        card_type = 'American Express'
        label = '1986'
        charge = stripe.Charge.construct_from({
            'id': '2404',
            'source': {
                'brand': card_type,
                'last4': label,
            },
        }, 'fake-key')

        with mock.patch.object(Stripe, 'get_address_from_token') as address_mock:
            address_mock.side_effect = Exception

            with mock.patch.object(stripe.Charge, 'create') as charge_mock:
                charge_mock.return_value = charge
                response = self.client.post(self.path, data)

            address_mock.assert_called_once_with(data['stripe_token'])

        self.assert_successful_order_response(response, basket.order_number)
        self.assert_order_created(basket, None, card_type, label)

    def test_successful_payment(self):
        basket = self.create_basket()
        data = self.generate_form_data(basket.id)
        card_type = 'American Express'
        label = '1986'
        charge = stripe.Charge.construct_from({
            'id': '2404',
            'source': {
                'brand': card_type,
                'last4': label,
            },
        }, 'fake-key')

        billing_address = BillingAddressFactory()
        with mock.patch.object(Stripe, 'get_address_from_token') as address_mock:
            address_mock.return_value = billing_address

            with mock.patch.object(stripe.Charge, 'create') as charge_mock:
                charge_mock.return_value = charge
                response = self.client.post(self.path, data)

            address_mock.assert_called_once_with(data['stripe_token'])

        self.assert_successful_order_response(response, basket.order_number)
        self.assert_order_created(basket, billing_address, card_type, label)

    def test_successful_payment_for_bulk_purchase(self):
        """
        Verify that when a Order has been successfully placed for bulk
        purchase then that order is linked to the provided business client.
        """
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)

        course = CourseFactory(partner=self.partner)
        course.create_or_update_seat('verified', True, 50, create_enrollment_code=True)
        basket = create_basket(owner=self.user, site=self.site)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        basket.add_product(enrollment_code, quantity=1)
        basket.strategy = Selector().strategy()

        data = self.generate_form_data(basket.id)
        data.update({'organization': 'Dummy Business Client'})
        data.update({PURCHASER_BEHALF_ATTRIBUTE: 'False'})

        # Manually add organization attribute on the basket for testing
        basket_add_organization_attribute(basket, data)

        card_type = 'American Express'
        label = '1986'
        charge = stripe.Charge.construct_from({
            'id': '2404',
            'source': {
                'brand': card_type,
                'last4': label,
            },
        }, 'fake-key')

        billing_address = BillingAddressFactory()
        with mock.patch.object(Stripe, 'get_address_from_token') as address_mock:
            address_mock.return_value = billing_address

            with mock.patch.object(stripe.Charge, 'create') as charge_mock:
                charge_mock.return_value = charge
                response = self.client.post(self.path, data)

            address_mock.assert_called_once_with(data['stripe_token'])

        self.assert_successful_order_response(response, basket.order_number)
        self.assert_order_created(basket, billing_address, card_type, label)

        # Now verify that a new business client has been created and current
        # order is now linked with that client through Invoice model.
        order = Order.objects.filter(basket=basket).first()
        business_client = BusinessClient.objects.get(name=data['organization'])
        assert Invoice.objects.get(order=order).business_client == business_client
