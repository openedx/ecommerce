import httpretty

from django.core.urlresolvers import reverse

from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.mixins import CouponMixin, LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')


class CouponReportCSVViewTest(CouponMixin, CourseCatalogTestMixin, LmsApiMockMixin, TestCase):
    """Unit tests for getting coupon report."""

    def setUp(self):
        super(CouponReportCSVViewTest, self).setUp()
        self.user = self.create_user(full_name="CouponReportCSVViewTest User", is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.course = CourseFactory(id='edX/DemoX/Demo_Course')
        self.coupon1 = self.create_coupon(
            partner_name="Partner 1",
            catalog_name="Test Catalog 1",
            course=self.course
        )

        self.coupon2 = self.create_coupon(
            partner_name="Partner 2",
            catalog_name="Test Catalog 2",
            course=self.course
        )

    @httpretty.activate
    def test_get_csv_report_for_specific_coupon(self):
        """
        Test the get method.
        CSV voucher report should contain coupon specific voucher data.
        """
        client_user = factories.UserFactory()
        self.mock_course_api_response(course=self.course)

        basket = Basket.get_basket(client_user, self.site)
        basket.add_product(self.coupon1)
        report_url = reverse('api:v2:coupons:coupon_reports', args=[self.coupon1.id])
        response = self.client.get(report_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.content.splitlines()), 6)

        basket = Basket.get_basket(client_user, self.site)
        basket.add_product(self.coupon2)
        report_url = reverse('api:v2:coupons:coupon_reports', args=[self.coupon2.id])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.content.splitlines()), 6)
