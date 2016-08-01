import httpretty
from django.test import RequestFactory
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.voucher.views import CouponReportCSVView
from ecommerce.tests.factories import PartnerFactory
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Catalog = get_model('catalogue', 'Catalog')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')


class CouponReportCSVViewTest(CouponMixin, LmsApiMockMixin, TestCase):
    """Unit tests for getting coupon report."""

    def setUp(self):
        super(CouponReportCSVViewTest, self).setUp()

        self.user = self.create_user(full_name="Test User", is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory()
        self.verified_seat = self.course.create_or_update_seat('verified', False, 0, self.partner)

        self.stock_record = StockRecord.objects.filter(product=self.verified_seat).first()

        self.first_coupon = self.create_new_coupon(catalog_name='Test catalog 1', partner_name='Tester1')
        self.second_coupon = self.create_new_coupon(catalog_name='Test catalog 2', partner_name='Tester2')

    def create_new_coupon(self, catalog_name, partner_name):
        """
        Create new coupon for testing CSV report generation
        """
        partner = PartnerFactory(name=partner_name)
        catalog = Catalog.objects.create(name=catalog_name, partner=partner)
        catalog.stock_records.add(self.stock_record)
        self.create_coupon(partner=partner, catalog=catalog)
        return self.coupon

    def request_specific_voucher_report(self, coupon):
        client = factories.UserFactory()
        basket = Basket.get_basket(client, self.site)
        basket.add_product(coupon)

        request = RequestFactory()
        response = CouponReportCSVView().get(request, coupon_id=coupon.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.content.splitlines()), 3)

    @httpretty.activate
    def test_get_csv_report_for_specific_coupon(self):
        """
        Test the get method.
        CSV voucher report should contain coupon specific voucher data.
        """
        self.mock_course_api_response(course=self.course)
        self.request_specific_voucher_report(self.first_coupon)
        self.request_specific_voucher_report(self.second_coupon)
