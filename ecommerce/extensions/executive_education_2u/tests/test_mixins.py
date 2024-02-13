import json

from oscar.core.loading import get_class, get_model
from oscar.test.factories import BasketFactory, ProductFactory

from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.executive_education_2u.mixins import ExecutiveEducation2UOrderPlacementMixin
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.extensions.test.factories import create_basket
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.mixins import BusinessIntelligenceMixin
from ecommerce.tests.testcases import TransactionTestCase

Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')


class EdxOrderPlacementMixinTests(
    BusinessIntelligenceMixin,
    PaymentEventsMixin,
    RefundTestMixin,
    TransactionTestCase
):
    def setUp(self):
        super(EdxOrderPlacementMixinTests, self).setUp()

        self.mock_address = {
            'address_line1': '10 Lovely Street',
            'city': 'Herndon',
            'postal_code': '00000',
            'state': 'state',
            'state_code': 'state_code',
            'country': 'country',
            'country_code': 'country_code',
        }
        self.mock_user_details = {
            'first_name': 'John',
            'last_name': 'Smith',
            'date_of_birth': '2000-01-01',
            'mobile_phone': '1234567890'
        }
        self.mock_terms_accepted_at = '2022-08-05T15:28:46.493Z',
        self.mock_data_share_consent = True
        self.expected_data_share_consent = 'true'

        # Ensure that the basket attribute type exists for these tests
        self.basket_attribute_type, _ = BasketAttributeType.objects.get_or_create(
            name=EMAIL_OPT_IN_ATTRIBUTE)

    def test_order_note_created(self):
        basket = create_basket(empty=True)
        basket.add_product(ProductFactory(stockrecords__price_excl_tax=0))

        expected_note = json.dumps({
            'address': self.mock_address,
            'user_details': self.mock_user_details,
            'terms_accepted_at': self.mock_terms_accepted_at,
            'data_share_consent': self.expected_data_share_consent,
        })
        order = ExecutiveEducation2UOrderPlacementMixin().place_free_order(
            basket,
            self.mock_address,
            self.mock_user_details,
            self.mock_terms_accepted_at,
            self.mock_data_share_consent,
        )

        self.assertEqual(basket.status, Basket.SUBMITTED)
        self.assertEqual(order.notes.first().message, expected_note)

    def test_non_free_basket_order(self):
        basket = create_basket(empty=True)
        basket.add_product(ProductFactory(stockrecords__price_excl_tax=10))
        with self.assertRaises(BasketNotFreeError):
            ExecutiveEducation2UOrderPlacementMixin().place_free_order(
                basket,
                self.mock_address,
                self.mock_user_details,
                self.mock_terms_accepted_at,
                self.mock_data_share_consent,
            )
