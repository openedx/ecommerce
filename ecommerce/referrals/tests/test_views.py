from datetime import datetime, timedelta

from django.core.urlresolvers import reverse
from oscar.test.factories import OrderFactory
from pytz import UTC

from ecommerce.extensions.refund.tests.factories import RefundFactory
from ecommerce.referrals.tests.factories import ReferralFactory
from ecommerce.tests.testcases import TestCase


class ValidationReportCsvViewTests(TestCase):
    def setUp(self):
        super(ValidationReportCsvViewTests, self).setUp()
        self.user = self.create_user(username="test_affiliate_partner")
        self.client.login(username=self.user.username, password=self.password)
        self.path = reverse('referrals:validation-report', kwargs={'affiliate_partner': self.user.username})

        # create standard order
        self.order = OrderFactory()
        ReferralFactory(order=self.order, affiliate_id=self.user.username)

        # create a refunded order
        self.refunded_order = OrderFactory()
        ReferralFactory(order=self.refunded_order, affiliate_id=self.user.username)
        RefundFactory(user=self.user, order=self.refunded_order)

        # create an old order
        self.old_order_date = datetime.utcnow() - timedelta(days=25)
        self.old_order_date = self.old_order_date.replace(tzinfo=UTC)
        self.old_order = OrderFactory()
        self.old_order.date_placed = self.old_order_date
        self.old_order.save()
        ReferralFactory(order=self.old_order, affiliate_id=self.user.username)

    def test_unauthorized_affiliate(self):
        """ Verify a 404 error is raised for an affiliate. """
        unauthorized_path = reverse('referrals:validation-report', kwargs={'affiliate_partner': 'fake_affiliate'})
        response = self.client.get(unauthorized_path)
        self.assertEqual(response.status_code, 404)

    def test_successful_response(self):
        """ Verify a successful response is returned. """
        response = self.client.get(self.path)
        expected_order = "{order_number},{date},ACCEPTED".format(
            order_number=self.order.number,
            date=self.order.date_placed.strftime("%d/%m/%Y %H:%M:%S")
        )
        expected_refund = "{order_number},{date},DECLINED,Order refunded".format(
            order_number=self.refunded_order.number,
            date=self.refunded_order.date_placed.strftime("%d/%m/%Y %H:%M:%S")
        )

        self.assertEqual(response['content-type'], 'text/csv')
        self.assertContains(response, expected_order)
        self.assertContains(response, expected_refund)
        self.assertNotContains(response, self.old_order.number)

    def test_successful_response_date(self):
        """ Verify a successful response is returned. """
        date = self.old_order_date.strftime("%Y-%m-%d")
        response = self.client.get("{path}?date={date}".format(path=self.path, date=date))
        expected_old_order = "{order_number},{date},ACCEPTED".format(
            order_number=self.old_order.number,
            date=self.old_order.date_placed.strftime("%d/%m/%Y %H:%M:%S")
        )

        self.assertEqual(response['content-type'], 'text/csv')
        self.assertContains(response, expected_old_order)
        self.assertNotContains(response, self.order.number)
        self.assertNotContains(response, self.refunded_order.number)
