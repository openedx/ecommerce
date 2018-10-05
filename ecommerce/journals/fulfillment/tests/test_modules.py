""" Tests of the Journal's fulfillment modules. """
import mock
from oscar.core.loading import get_model
from oscar.test import factories
from requests.exceptions import ConnectionError, HTTPError
from slumber.exceptions import HttpClientError

from ecommerce.extensions.fulfillment.status import LINE
from ecommerce.extensions.test.factories import create_order
from ecommerce.journals.constants import JOURNAL_PRODUCT_CLASS_NAME
from ecommerce.journals.fulfillment.modules import JournalFulfillmentModule
from ecommerce.journals.tests.mixins import JournalMixin  # pylint: disable=no-name-in-module
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ProductAttribute = get_model('catalogue', 'ProductAttribute')


class JournalFulfillmentModuleTest(TestCase, JournalMixin):
    """ Test Journal fulfillment. """

    def setUp(self):
        super(JournalFulfillmentModuleTest, self).setUp()
        user = self.create_user(is_staff=True)
        self.client.login(username=user.username, password=self.password)
        basket = factories.BasketFactory(owner=user, site=self.site)
        basket.add_product(
            self.create_product(self.client),
            1
        )
        self.order = create_order(number=1, basket=basket, user=user)
        self.lines = self.order.lines.all()

    def test_supports_line(self):
        """ Test that a line containing Journal returns True. """
        supports_line = JournalFulfillmentModule().supports_line(self.lines[0])
        self.assertTrue(supports_line)

    def test_get_supported_lines(self):
        """ Test that Journal lines where returned. """
        supported_lines = JournalFulfillmentModule().get_supported_lines(self.lines)
        self.assertEqual(len(supported_lines), 1)

    @mock.patch("ecommerce.journals.fulfillment.modules.post_journal_access")
    def test_fulfill_product(self, mocked_post_journal_access):
        """ Test fulfilling a Journal product. """
        __, completed_lines = JournalFulfillmentModule().fulfill_product(self.order, self.lines)
        mocked_post_journal_access.assert_called_once_with(
            site_configuration=self.order.site.siteconfiguration,
            order_number=self.order.number,
            username=self.order.user.username,
            journal_uuid=self.order.lines.first().product.attr.UUID
        )
        self.assertEqual(
            completed_lines[0].status,
            LINE.COMPLETE
        )

    def test_fulfill_product_without_attribute(self):
        """ Test fulfilling a Journal product with raising the AttributeError exception """
        ProductAttribute.objects.get(product_class__name=JOURNAL_PRODUCT_CLASS_NAME, code='UUID').delete()
        __, completed_lines = JournalFulfillmentModule().fulfill_product(self.order, self.lines)
        self.assertEqual(
            completed_lines[0].status,
            LINE.FULFILLMENT_CONFIGURATION_ERROR
        )

    @mock.patch("ecommerce.journals.fulfillment.modules.post_journal_access", mock.Mock(side_effect=ConnectionError))
    def test_fulfill_with_error(self):
        """ Test fulfilling a Journal product with raising the ConnectionError exception """
        __, completed_lines = JournalFulfillmentModule().fulfill_product(self.order, self.lines)
        self.assertEqual(
            completed_lines[0].status,
            LINE.FULFILLMENT_NETWORK_ERROR
        )

    @mock.patch("ecommerce.journals.fulfillment.modules.post_journal_access", mock.Mock(side_effect=HttpClientError))
    def test_fulfill_with_client_error(self):
        """ Test fulfilling a Journal product with raising the ConnectionError exception """
        __, completed_lines = JournalFulfillmentModule().fulfill_product(self.order, self.lines)
        self.assertEqual(
            completed_lines[0].status,
            LINE.FULFILLMENT_SERVER_ERROR
        )

    @mock.patch("ecommerce.journals.fulfillment.modules.post_journal_access", mock.Mock(side_effect=Exception))
    def test_fulfill_with_base_error(self):
        """ Test fulfilling a Journal product with raising the base exception """
        __, completed_lines = JournalFulfillmentModule().fulfill_product(self.order, self.lines)
        self.assertEqual(
            completed_lines[0].status,
            LINE.FULFILLMENT_SERVER_ERROR
        )

    @mock.patch("ecommerce.journals.fulfillment.modules.revoke_journal_access", mock.Mock(return_value=''))
    def test_revoke_line(self):
        self.assertTrue(JournalFulfillmentModule().revoke_line(self.lines[0]))

    @mock.patch("ecommerce.journals.fulfillment.modules.revoke_journal_access", mock.Mock(side_effect=HTTPError))
    def test_revoke_line_invalid_order_number(self):
        self.assertFalse(JournalFulfillmentModule().revoke_line(self.lines[0]))

    @mock.patch("ecommerce.journals.fulfillment.modules.revoke_journal_access")
    def test_revoke_product(self, mocked_revoke_journal_access):
        """ Test revoking a Journal product. """
        JournalFulfillmentModule().revoke_line(self.lines[0])
        mocked_revoke_journal_access.assert_called_once_with(
            site_configuration=self.lines[0].order.site.siteconfiguration,
            order_number=self.lines[0].order.number
        )
