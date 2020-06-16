

from uuid import uuid4

import httpretty
from django.test import RequestFactory
from oscar.core.loading import get_model

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.voucher.views import CouponReportCSVView
from ecommerce.tests.factories import PartnerFactory, UserFactory
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')


class CouponReportCSVViewTest(CouponMixin, DiscoveryTestMixin, LmsApiMockMixin, TestCase):
    """Unit tests for getting coupon report."""

    def setUp(self):
        super(CouponReportCSVViewTest, self).setUp()

        self.user = self.create_user(full_name="Test User", is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory(partner=self.partner)
        self.verified_seat = self.course.create_or_update_seat('verified', False, 0)

        self.stock_record = StockRecord.objects.filter(product=self.verified_seat).first()

        partner1 = PartnerFactory(name='Tester1')
        catalog1 = Catalog.objects.create(name="Test catalog 1", partner=partner1)
        catalog1.stock_records.add(self.stock_record)
        self.coupon1 = self.create_coupon(partner=partner1, catalog=catalog1)
        self.coupon1.history.all().update(history_user=self.user)
        partner2 = PartnerFactory(name='Tester2')
        catalog2 = Catalog.objects.create(name="Test catalog 2", partner=partner2)
        catalog2.stock_records.add(self.stock_record)
        self.coupon2 = self.create_coupon(partner=partner2, catalog=catalog2)
        self.coupon2.history.all().update(history_user=self.user)
        self.coupon3 = self.create_coupon(
            partner=partner1,
            enterprise_customer=str(uuid4()),
            enterprise_customer_catalog=str(uuid4())
        )
        self.coupon3.history.all().update(history_user=self.user)

    def request_specific_voucher_report(self, coupon):
        client = UserFactory()
        basket = Basket.get_basket(client, self.site)
        basket.add_product(coupon)

        request = RequestFactory()
        response = CouponReportCSVView().get(request, coupon_id=coupon.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.content.splitlines()), 7)

    @httpretty.activate
    def test_get_csv_report_for_specific_coupon(self):
        """
        Test the get method.
        CSV voucher report should contain coupon specific voucher data.
        """
        self.mock_course_api_response(course=self.course)
        self.request_specific_voucher_report(self.coupon1)
        self.request_specific_voucher_report(self.coupon2)
        self.request_specific_voucher_report(self.coupon3)

    def test_report_missing_stockrecord_raises_http404(self):
        """ Verify that Http404 is raised when no StockRecord for coupon """
        StockRecord.objects.get(product=self.coupon1).delete()
        request = RequestFactory().get('')
        response = CouponReportCSVView().get(request, self.coupon1.id)
        self.assertEqual(response.content.decode('utf-8'),
                         'Failed to find a matching stock record for coupon, report download canceled.')
        self.assertEqual(response.status_code, 404)
