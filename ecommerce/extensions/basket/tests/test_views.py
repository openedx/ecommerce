# TODO Restore these once the factories built for multi-tenancy have been merged.
# from decimal import Decimal
#
# from django.core.urlresolvers import reverse
# from django.test import TestCase
# import factory
# from oscar.core.loading import get_class, get_model
# from oscar.test import newfactories as factories
#
# Basket = get_model('basket', 'Basket')
# Selector = get_class('partner.strategy', 'Selector')


# # TODO Create our own factories to support multi-tenancy
# class PartnerFactory(factory.DjangoModelFactory):
#     name = factory.Sequence(lambda n: 'Partner %d' % n)
#     short_code = factory.Sequence(lambda n: 'P_%d' % n)
#
#     class Meta:
#         model = get_model('partner', 'Partner')
#
#     @factory.post_generation
#     def users(self, create, extracted, **kwargs):
#         if not create:
#             return
#
#         if extracted:
#             for user in extracted:
#                 self.users.add(user)
#
#
# class StockRecordFactory(factory.DjangoModelFactory):
#     partner = factory.SubFactory(PartnerFactory)
#     partner_sku = factory.Sequence(lambda n: 'unit%d' % n)
#     price_currency = "GBP"
#     price_excl_tax = Decimal('9.99')
#     num_in_stock = 100
#
#     class Meta:
#         model = get_model('partner', 'StockRecord')


# TODO Restore these once the factories built for multi-tenancy have been merged.
# class BasketSingleItemViewTests(TestCase):
#     path = reverse('basket:single-item')
#
#     def setUp(self):
#         password = 'password'
#         self.user = factories.UserFactory(password=password)
#         self.client.login(username=self.user.username, password=password)
#
#         product = factories.ProductFactory()
#         self.stock_record = StockRecordFactory(product=product)
#
#     def test_login_required(self):
#         """ The view should require the user to be logged in. """
#         self.client.logout()
#         response = self.client.get(self.path, follow=True)
#         self.assertRedirects(response, reverse('login'))
#
#     # TODO Add the partner to the request using middleware
#     # def test_missing_partner(self):
#     #     """ The view should return HTTP 500 if the site has no associated Partner. """
#     #     self.fail()
#
#     def test_missing_sku(self):
#         """ The view should return HTTP 400 if no SKU is provided. """
#         response = self.client.get(self.path)
#         self.assertEqual(response.status_code, 400)
#
#     def test_unavailable_product(self):
#         """ The view should return HTTP 400 if the product is not available for purchase. """
#         product = self.stock_record.product
#         self.stock_record.num_in_stock = 0
#         self.stock_record.save()
#         self.assertFalse(Selector().strategy().fetch_for_product(product).availability.is_available_to_buy)
#
#         url = '{path}?sku={sku}'.format(path=self.path, sku=self.stock_record.partner_sku)
#         response = self.client.get(url)
#         self.assertEqual(response.status_code, 400)
#
#     def assert_view_redirects_to_checkout_payment(self):
#         """ Verify the view redirects to the checkout payment page. """
#         url = '{path}?sku={sku}'.format(path=self.path, sku=self.stock_record.partner_sku)
#         response = self.client.get(url)
#         self.assertRedirects(response, reverse('checkout:payment'), 303)
#
#     def test_basket(self):
#         """ The user's latest Basket should contain one instance of the specified product and be frozen. """
#         self.assert_view_redirects_to_checkout_payment()
#
#         basket = Basket.get_basket(self.user)
#         self.assertEqual(basket.status, Basket.OPEN)
#         self.assertEqual(basket.lines.count(), 1)
#         self.assertEqual(basket.lines.first().product, self.stock_record.product)
#
#     def test_redirect(self):
#         """ The view should redirect the user to the payment page. """
#         self.assert_view_redirects_to_checkout_payment()
