from django.test import RequestFactory
from oscar.core.loading import get_model

from ecommerce.extensions.voucher.views import CouponReportCSVView
from ecommerce.tests.factories import PartnerFactory
from ecommerce.tests.mixins import CouponMixin
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')


class CouponReportCSVViewTest(CouponMixin, TestCase):
    """Unit tests for getting coupon report."""

    def setUp(self):
        super(CouponReportCSVViewTest, self).setUp()
        partner1 = PartnerFactory(name='Tester1')
        catalog1 = Catalog.objects.create(name="Test catalog 1", partner=partner1)
        self.coupon1 = self.create_coupon(partner=partner1, catalog=catalog1)
        partner2 = PartnerFactory(name='Tester2')
        catalog2 = Catalog.objects.create(name="Test catalog 2", partner=partner2)
        self.coupon2 = self.create_coupon(partner=partner2, catalog=catalog2)

    def request_specific_voucher_report(self, coupon_id):
        request = RequestFactory()
        response = CouponReportCSVView().get(request, coupon_id=coupon_id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.content.splitlines()), 6)

    def test_get_csv_report_for_specific_coupon(self):
        """
        Test the get method.
        CSV voucher report should contain coupon specific voucher data.
        """
        self.request_specific_voucher_report(self.coupon1.id)
        self.request_specific_voucher_report(self.coupon2.id)
