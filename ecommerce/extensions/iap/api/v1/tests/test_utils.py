import mock

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.iap.api.v1.utils import products_in_basket_already_purchased
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder
from ecommerce.extensions.test.factories import create_basket, create_order
from ecommerce.tests.testcases import TestCase


class TestProductsInBasketPurchased(TestCase):
    """ Tests for products_in_basket_already_purchased method. """

    def setUp(self):
        super(TestProductsInBasketPurchased, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory(partner=self.partner)
        product = self.course.create_or_update_seat('verified', False, 50)
        self.basket = create_basket(
            owner=self.user, site=self.site, price='50.0', product_class=product.product_class
        )
        create_order(site=self.site, user=self.user, basket=self.basket)

    def test_already_purchased(self):
        """
        Test products in basket already purchased by user
        """
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=True):
            return_value = products_in_basket_already_purchased(self.user, self.basket, self.site)
            self.assertTrue(return_value)

    def test_not_purchased_yet(self):
        """
        Test products in basket not yet purchased by user
        """
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=False):
            return_value = products_in_basket_already_purchased(self.user, self.basket, self.site)
            self.assertFalse(return_value)
