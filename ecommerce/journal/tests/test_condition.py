import mock
from oscar.core.loading import get_model
from requests.exceptions import Timeout
from slumber.exceptions import HttpNotFoundError, SlumberBaseException

from ecommerce.extensions.test import factories
from ecommerce.journal.tests.mixins import JournalMixin     # pylint: disable=no-name-in-module
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')
LOGGER_NAME = 'ecommerce.journal.conditions'


@mock.patch("ecommerce.journal.conditions.fetch_journal_bundle")
class JournalBundleConditionTests(TestCase, JournalMixin):
    def setUp(self):
        super(JournalBundleConditionTests, self).setUp()
        user = self.create_user(is_staff=True)
        self.client.login(username=user.username, password=self.password)

        self.condition = factories.JournalConditionFactory()
        self.offer = factories.JournalBundleOfferFactory(site=self.site, condition=self.condition)
        self.basket = factories.BasketFactory(site=self.site, owner=factories.UserFactory())
        self.basket.add_product(
            self.create_product(self.client),
            1
        )

    def test_name(self, mocked_journal_api_response):
        """ The name should contain the program's UUID. """
        mocked_journal_api_response.return_value = None
        expected = 'Basket contains every product in bundle {}'.format(self.condition.journal_bundle_uuid)
        self.assertEqual(self.condition.name, expected)

    def test_is_satisfied_with_empty_basket(self, mocked_journal_api_response):
        """ Test the 'is_satisfied' with empty basket """
        mocked_journal_api_response.return_value = None
        self.basket.flush()
        self.assertTrue(self.basket.is_empty)
        self.assertFalse(self.condition.is_satisfied(self.offer, self.basket))

    def test_is_satisfied_with_exception(self, mocked_journal_api_response):
        """ Test the 'is_satisfied' with 'HttpNotFoundError' exception  """
        mocked_journal_api_response.side_effect = HttpNotFoundError
        self.assertFalse(self.condition.is_satisfied(self.offer, self.basket))

    def test_is_satisfied_with_slumber_exception(self, mocked_journal_api_response):
        """ Test the 'is_satisfied' with 'SlumberBaseException' exception  """
        mocked_journal_api_response.side_effect = SlumberBaseException
        self.assertFalse(self.condition.is_satisfied(self.offer, self.basket))

    def test_is_satisfied_with_timeout(self, mocked_journal_api_response):
        """ Test the 'is_satisfied' with 'Timeout' exception  """
        mocked_journal_api_response.side_effect = Timeout
        self.assertFalse(self.condition.is_satisfied(self.offer, self.basket))

    def test_is_satisfied_without_journal_bundle(self, mocked_journal_api_response):
        """ Test the 'is_satisfied' without Journal bundle """
        mocked_journal_api_response.return_value = None
        self.assertFalse(self.condition.is_satisfied(self.offer, self.basket))

    def test_is_satisfied_without_courses(self, mocked_journal_api_response):
        """ Test the 'is_satisfied' without courses in Journal bundle """
        mocked_journal_api_response.return_value = self.get_mocked_discovery_journal_bundle(empty_courses=True)
        self.assertFalse(self.condition.is_satisfied(self.offer, self.basket))

    def test_is_satisfied_with_some_but_not_all_courses(self, mocked_journal_api_response):
        """ Test the 'is_satisfied' with only some of the courses in the Journal bundle """
        mocked_journal_api_response.return_value = self.get_mocked_discovery_journal_bundle(multiple_courses=True)
        self.assertFalse(self.condition.is_satisfied(self.offer, self.basket))

    def test_is_satisfied_with_dummy_product(self, mocked_journal_api_response):
        """ Test the 'is_satisfied' with dummy product in basket """
        mocked_journal_api_response.return_value = self.get_mocked_discovery_journal_bundle()
        self.basket.flush()
        self.basket.add_product(
            self.create_product(
                self.client,
                data=self.get_data_for_create(sku="dummy-sku")
            ),
            1
        )
        self.assertFalse(self.condition.is_satisfied(self.offer, self.basket))

    def test_is_satisfied_with_valid_data(self, mocked_journal_api_response):
        """ Test the 'is_satisfied' with valid Journal bundle """
        mocked_journal_api_response.return_value = self.get_mocked_discovery_journal_bundle(empty_journals=True)
        self.assertTrue(self.condition.is_satisfied(self.offer, self.basket))

    def test_get_applicable_lines(self, mocked_journal_api_response):
        """ Test the 'get_applicable_lines' with valid product in basket """
        mocked_journal_api_response.return_value = self.get_mocked_discovery_journal_bundle()
        applicable_lines = [
            (line.product.stockrecords.first().price_excl_tax, line) for line in self.basket.all_lines()
        ]
        self.assertEqual(self.condition.get_applicable_lines(self.offer, self.basket), applicable_lines)

    def test_get_applicable_lines_with_empty_basket(self, mocked_journal_api_response):
        """ Test the 'get_applicable_lines' with empty basket """
        mocked_journal_api_response.return_value = self.get_mocked_discovery_journal_bundle()
        self.basket.flush()
        self.assertEqual(self.condition.get_applicable_lines(self.offer, self.basket), [])

    def test_get_applicable_lines_sku_not_in_basket(self, mocked_journal_api_response):
        """ Test the 'get_applicable_lines' where the sku is not in the basket """
        mocked_journal_api_response.return_value = self.get_mocked_discovery_journal_bundle()
        self.basket.flush()
        self.basket.add_product(
            self.create_product(
                self.client,
                data=self.get_data_for_create(sku="dummy-sku")
            ),
            1
        )
        self.assertEqual(self.condition.get_applicable_lines(self.offer, self.basket), [])

    @mock.patch("ecommerce.extensions.catalogue.models.Product.get_is_discountable")
    def test_get_applicable_lines_product_is_not_discountable(
            self, mocked_product_is_discountable, mocked_journal_api_response):
        """ Test the 'get_applicable_lines' where the product is not discountable """
        mocked_journal_api_response.return_value = self.get_mocked_discovery_journal_bundle()
        mocked_product_is_discountable.return_value = False

        self.assertEqual(self.condition.get_applicable_lines(self.offer, self.basket), [])

    @mock.patch("oscar.apps.offer.utils.unit_price")
    def test_get_applicable_lines_no_price(self, mocked_unit_price, mocked_journal_api_response):
        """ Test the 'get_applicable_lines' where there is no price """
        mocked_journal_api_response.return_value = self.get_mocked_discovery_journal_bundle()
        mocked_unit_price.return_value = None
        self.assertEqual(self.condition.get_applicable_lines(self.offer, self.basket), [])

    def test_get_applicable_lines_no_journal_bundle(self, mock_journal_api_response):
        """ Test 'get_applicable_lines' where the journal bundle is None """
        mock_journal_api_response.return_value = None
        self.assertEqual(self.condition.get_applicable_lines(self.offer, self.basket), [])
