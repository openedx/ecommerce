import itertools

from django.contrib.sites.models import Site
from oscar.core.loading import get_class, get_model
from oscar.test import factories

from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class BasketTests(TestCase):
    def setUp(self):
        super(BasketTests, self).setUp()
        self.site1 = Site.objects.create(domain='site1.fake')
        self.site2 = Site.objects.create(domain='site2.fake')

    def assert_basket_state(self, basket, status, user, site):
        """ Verify the given basket's properties. """
        self.assertEqual(basket.status, status)
        self.assertEqual(basket.owner, user)
        self.assertEqual(basket.site, site)

    def _create_basket(self, user, site, status=Basket.OPEN):
        """ Create a new Basket for the user. """
        basket = factories.create_basket()
        basket.owner = user
        basket.site = site
        basket.status = status
        basket.save()
        return basket

    def test_order_number(self):
        """ The method should return the order number for the Order corresponding to the Basket. """
        basket = factories.create_basket()
        expected = OrderNumberGenerator().order_number(basket)
        self.assertEqual(basket.order_number, expected)

    def test_unicode(self):
        """ Verify the __unicode__ method returns the correct value. """
        basket = factories.create_basket()
        expected = u"{id} - {status} basket (owner: {owner}, lines: {num_lines})".format(
            id=basket.id,
            status=basket.status,
            owner=basket.owner,
            num_lines=basket.num_lines
        )

        self.assertEqual(unicode(basket), expected)

    def test_get_basket_without_existing_baskets(self):
        """ If the user has no existing baskets, the method should return a new one. """
        user = factories.UserFactory()
        self.assertEqual(user.baskets.count(), 0, 'A new user should not have any associated Baskets.')

        basket = Basket.get_basket(user, self.site1)

        # Check the basic details of the new basket
        self.assert_basket_state(basket, Basket.OPEN, user, self.site1)

        self.assertEqual(len(basket.all_lines()), 0, 'The new basket should be empty')
        self.assertEqual(user.baskets.count(), 1, 'No basket was created for the user.')

        # Verify we create new baskets for other sites/tenants
        basket = Basket.get_basket(user, self.site2)
        self.assert_basket_state(basket, Basket.OPEN, user, self.site2)
        self.assertEqual(len(basket.all_lines()), 0, 'The new basket should be empty')
        self.assertEqual(user.baskets.count(), 2, 'A new basket was not created for the second site.')

    def test_get_basket_with_existing_baskets(self):
        """ If the user has existing baskets in editable states, the method should return a single merged basket. """
        user = factories.UserFactory()

        # Create baskets in a state that qualifies them for merging
        editable_baskets = []
        for status in Basket.editable_statuses:
            editable_baskets.append(self._create_basket(user, self.site1, status))

        # Create baskets that should NOT be merged
        non_editable_baskets = []
        for status in (Basket.MERGED, Basket.FROZEN, Basket.SUBMITTED):
            non_editable_baskets.append(self._create_basket(user, self.site1, status))

        # Create a basket for the other site/tenant
        Basket.get_basket(user, self.site2)

        self.assertEqual(user.baskets.count(), 6)

        basket = Basket.get_basket(user, self.site1)

        # No new basket should be created
        self.assertEqual(user.baskets.count(), 6)

        # Check the basic details of the new basket
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.owner, user)

        # One of the previously editable baskets should be in the merged state.
        actual_states = [Basket.objects.get(id=eb.id).status for eb in editable_baskets]
        self.assertEqual(actual_states, [Basket.OPEN, Basket.MERGED])

        # The merged basket should include the products from the original baskets
        expected_lines = list(itertools.chain.from_iterable([list(eb.lines.all()) for eb in editable_baskets]))
        self.assertEqual(list(basket.lines.all()), expected_lines)

        # Verify the basket for the second site/tenant is not modified
        self.assert_basket_state(user.baskets.get(site=self.site2), Basket.OPEN, user, self.site2)

    def test_create_basket(self):
        """ Verify the method creates a new basket. """
        user = factories.UserFactory()
        basket = Basket.create_basket(self.site1, user)
        self.assertEqual(basket.site, self.site1)
        self.assertEqual(basket.owner, user)
