

import ddt
import mock
from django.core.management import call_command
from oscar.core.loading import get_model
from oscar.test.factories import OrderLineFactory

from ecommerce.courses.publishers import LMSPublisher
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.models import Product
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.testcases import TestCase

StockRecord = get_model('partner', 'StockRecord')


@ddt.ddt
class ConvertCourseTest(DiscoveryTestMixin, TestCase):
    @ddt.data(
        ('honor', 'honor_to_audit', ''),
        ('', 'audit_to_honor', 'honor')
    )
    @ddt.unpack
    def test_convert_course(self, initial_cert_type, direction, new_cert_type):
        """Verify that an honor course can be converted to audit correctly."""
        course = CourseFactory(partner=self.partner)
        seat_to_convert = course.create_or_update_seat(initial_cert_type, False, 0)
        stock_record = StockRecord.objects.get(product=seat_to_convert)
        order_line = OrderLineFactory(stockrecord=stock_record, product=seat_to_convert, partner_sku='test_sku')

        old_stock_record_sku = stock_record.partner_sku
        old_order_line_sku = order_line.partner_sku

        # Mock the LMS call
        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            mock_publish.return_value = True
            call_command('convert_course', course.id, commit=True, direction=direction, partner=self.partner.code)

        # Calling refresh_from_db doesn't seem to update the product's attributes
        seat_to_convert = Product.objects.get(pk=seat_to_convert.pk)
        stock_record.refresh_from_db()
        order_line.refresh_from_db()

        self.assertEqual(getattr(seat_to_convert.attr, 'certificate_type', ''), new_cert_type)

        if new_cert_type == '':
            self.assertNotIn('with honor certificate', seat_to_convert.title)
        else:
            self.assertIn(' with honor certificate', seat_to_convert.title)

        # Verify that partner SKUs are correctly updated
        self.assertNotEqual(old_stock_record_sku, stock_record.partner_sku)
        self.assertNotEqual(old_order_line_sku, order_line.partner_sku)
        self.assertEqual(order_line.partner_sku, stock_record.partner_sku)

        self.assertTrue(mock_publish.called)

    @ddt.data(
        ('honor', 'honor_to_audit', ''),
        ('', 'audit_to_honor', 'honor')
    )
    @ddt.unpack
    def test_without_commit(self, initial_cert_type, direction, new_cert_type):
        """Verify that the commit flag is necessary to run the command successfully."""
        course = CourseFactory(partner=self.partner)
        seat_to_convert = course.create_or_update_seat(initial_cert_type, False, 0)

        call_command('convert_course', course.id, commit=False, direction=direction, partner=self.partner.code)

        seat_to_convert = Product.objects.get(pk=seat_to_convert.pk)

        self.assertEqual(getattr(seat_to_convert.attr, 'certificate_type', ''), initial_cert_type)

        new_seats = [
            seat for seat in course.seat_products
            if getattr(seat.attr, 'certificate_type', '') == new_cert_type
        ]
        self.assertEqual(len(new_seats), 0)

    @ddt.data('honor_to_audit', 'audit_to_honor')
    def test_without_seats(self, direction):
        """Verify that the command fails when the course does not have the correct seat type."""
        course = CourseFactory()

        call_command('convert_course', course.id, commit=True, direction=direction, partner=self.partner)

        self.assertEqual(len(course.seat_products), 0)
