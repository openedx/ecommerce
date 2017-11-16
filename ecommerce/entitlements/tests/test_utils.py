from oscar.core.loading import get_model

from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.tests.testcases import TestCase

StockRecord = get_model('partner', 'StockRecord')


class TestCourseEntitlementProductCreation(TestCase):

    def setUp(self):
        super(TestCourseEntitlementProductCreation, self).setUp()

        self.partner = self.site.siteconfiguration.partner

    def test_course_entitlement_creation(self):
        """ Test course entitlement product creation """

        product = create_or_update_course_entitlement(
            'verified', 100, self.partner, 'foo-bar', 'Foo Bar Entitlement')
        self.assertEqual(product.title, 'Course Foo Bar Entitlement')
        self.assertEqual(product.attr.UUID, 'foo-bar')

        stock_record = StockRecord.objects.get(product=product, partner=self.partner)
        self.assertEqual(stock_record.price_excl_tax, 100)

    def test_course_entitlement_update(self):
        """ Test course entitlement product update """

        partner = self.site.siteconfiguration.partner
        product = create_or_update_course_entitlement('verified', 100, self.partner, 'foo-bar', 'Foo Bar Entitlement')
        stock_record = StockRecord.objects.get(product=product, partner=self.partner)

        self.assertEqual(stock_record.price_excl_tax, 100)
        self.assertEqual(product.title, 'Course Foo Bar Entitlement')

        product = create_or_update_course_entitlement('verified', 200, partner, 'foo-bar', 'Foo Bar Entitlement')

        stock_record = StockRecord.objects.get(product=product, partner=self.partner)
        self.assertEqual(stock_record.price_excl_tax, 200)
