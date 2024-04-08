"""Tests for the batch_update_mobile_seats command"""
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.utils.timezone import now, timedelta
from testfixtures import LogCapture

from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.models import Product
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.iap.management.commands.batch_update_mobile_seats import Command as mobile_seats_command
from ecommerce.extensions.iap.models import IAPProcessorConfiguration
from ecommerce.extensions.partner.models import StockRecord
from ecommerce.tests.testcases import TransactionTestCase

ANDROID_SKU_PREFIX = 'android'
IOS_SKU_PREFIX = 'ios'


class BatchUpdateMobileSeatsTests(DiscoveryTestMixin, TransactionTestCase):
    """
    Tests for the batch_update_mobile_seats command.
    """
    def setUp(self):
        super().setUp()
        self.command = 'batch_update_mobile_seats'

    def _create_course_and_seats(self, create_mobile_seats=False, expired_in_past=False):
        """
        Create the specified number of courses with audit and verified seats. Create mobile seats
        if specified.
        """
        course = CourseFactory(partner=self.partner)
        course.create_or_update_seat('audit', False, 0)
        verified_seat = course.create_or_update_seat('verified', True, Decimal(10.0))
        verified_seat.title = (
            f'Seat in {course.name} with verified certificate (and ID verification)'
        )
        expires = now() - timedelta(days=10) if expired_in_past else now() + timedelta(days=10)
        verified_seat.expires = expires
        verified_seat.save()
        if create_mobile_seats:
            self._create_mobile_seat_for_course(course, ANDROID_SKU_PREFIX)
            self._create_mobile_seat_for_course(course, IOS_SKU_PREFIX)

        return course

    def _get_web_seat_for_course(self, course):
        """ Get the default seat created for web for a course """
        return Product.objects.filter(
            parent__isnull=False,
            course=course,
            attributes__name="id_verification_required",
            parent__product_class__name="Seat"
        ).first()

    def _create_mobile_seat_for_course(self, course, sku_prefix):
        """ Create a mobile seat for a course given the sku_prefix """
        web_seat = self._get_web_seat_for_course(course)
        web_stock_record = web_seat.stockrecords.first()
        mobile_seat = Product.objects.create(
            course=course,
            parent=web_seat.parent,
            structure=web_seat.structure,
            expires=web_seat.expires,
            is_public=web_seat.is_public,
            title="{} {}".format(sku_prefix.capitalize(), web_seat.title.lower())
        )

        mobile_seat.attr.certificate_type = web_seat.attr.certificate_type
        mobile_seat.attr.course_key = web_seat.attr.course_key
        mobile_seat.attr.id_verification_required = web_seat.attr.id_verification_required
        mobile_seat.attr.save()

        StockRecord.objects.create(
            partner=web_stock_record.partner,
            product=mobile_seat,
            partner_sku="mobile.{}.{}".format(sku_prefix.lower(), web_stock_record.partner_sku.lower()),
            price_currency=web_stock_record.price_currency,
        )
        return mobile_seat

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_mobile_seat_for_new_course_run_created(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail):
        """Test that the command creates mobile seats for new course run."""
        course_with_mobile_seat = self._create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        course_run_without_mobile_seat = self._create_course_and_seats()
        course_run_return_value = {'course': course_with_mobile_seat.id}
        course_detail_return_value = {'course_run_keys': [course_run_without_mobile_seat.id]}

        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = course_run_return_value
        mock_course_detail.return_value = course_detail_return_value

        call_command(self.command)
        actual_mobile_seats = Product.objects.filter(
            course=course_run_without_mobile_seat,
            stockrecords__partner_sku__icontains='mobile'
        )
        expected_mobile_seats_count = 2
        self.assertTrue(actual_mobile_seats.exists())
        self.assertEqual(actual_mobile_seats.count(), expected_mobile_seats_count)

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_extra_seats_not_created(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail):
        """Test the case where mobile seats are already created for course run."""
        course_with_mobile_seat = self._create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        course_run_with_mobile_seat = self._create_course_and_seats(create_mobile_seats=True)
        course_run_return_value = {'course': course_with_mobile_seat.id}
        course_detail_return_value = {'course_run_keys': [course_run_with_mobile_seat.id]}

        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = course_run_return_value
        mock_course_detail.return_value = course_detail_return_value

        call_command(self.command)
        actual_mobile_seats = Product.objects.filter(
            course=course_run_with_mobile_seat,
            stockrecords__partner_sku__icontains='mobile'
        )
        expected_mobile_seats_count = 2
        self.assertTrue(actual_mobile_seats.exists())
        self.assertEqual(actual_mobile_seats.count(), expected_mobile_seats_count)

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_no_response_from_discovery_for_course_run_api(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail):
        """Test that the command handles exceptions if no response returned from Discovery for course run API."""
        course_with_mobile_seat = self._create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        course_run_without_mobile_seat = self._create_course_and_seats()
        course_run_return_value = None
        course_detail_return_value = {'course_run_keys': [course_run_without_mobile_seat.id]}

        logger_name = 'ecommerce.extensions.iap.management.commands.batch_update_mobile_seats'
        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = course_run_return_value
        mock_course_detail.return_value = course_detail_return_value

        with self.assertRaises(AttributeError), \
                LogCapture(logger_name) as logger:
            call_command(self.command)
            msg = "Error while fetching parent course for {} from discovery".format(course_with_mobile_seat.id)
            logger.check_present(logger_name, 'ERROR', msg)

        actual_mobile_seats = Product.objects.filter(
            course=course_run_without_mobile_seat,
            stockrecords__partner_sku__icontains='mobile'
        )
        self.assertFalse(actual_mobile_seats.exists())

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_no_response_from_discovery_for_course_detail_api(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail):
        """Test that the command handles exceptions if no response returned from Discovery for course detail API."""
        course_with_mobile_seat = self._create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        course_run_without_mobile_seat = self._create_course_and_seats()
        course_run_return_value = {'course': course_with_mobile_seat.id}

        logger_name = 'ecommerce.extensions.iap.management.commands.batch_update_mobile_seats'
        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = course_run_return_value
        mock_course_detail.return_value = None

        with self.assertRaises(AttributeError), \
                LogCapture(logger_name) as logger:
            call_command(self.command)
            msg = "Error while fetching course runs for {} from discovery".format(course_with_mobile_seat.id)
            logger.check_present(logger_name, 'ERROR', msg)

        actual_mobile_seats = Product.objects.filter(
            course=course_run_without_mobile_seat,
            stockrecords__partner_sku__icontains='mobile'
        )
        self.assertFalse(actual_mobile_seats.exists())

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_command_arguments_are_processed(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail):
        course_with_mobile_seat = self._create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = {'course': course_with_mobile_seat.id}
        mock_course_detail.return_value = {'course_run_keys': []}

        call_command(self.command, batch_size=1, sleep_time=1)
        assert mock_email.call_count == 1

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    def test_send_mail_to_mobile_team(self, mock_publish_to_lms, mock_course_run, mock_course_detail):
        logger_name = 'ecommerce.extensions.iap.management.commands.batch_update_mobile_seats'
        email_sender = 'ecommerce.extensions.communication.utils.Dispatcher.dispatch_direct_messages'
        mock_mobile_team_mail = 'abc@example.com'
        iap_configs = IAPProcessorConfiguration.get_solo()
        iap_configs.mobile_team_email = mock_mobile_team_mail
        iap_configs.save()
        course = self._create_course_and_seats(create_mobile_seats=True, expired_in_past=True)

        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = {'course': course.id}
        mock_course_detail.return_value = {'course_run_keys': []}
        mock_email_body = {
            'subject': 'Expired Courses with mobile SKUS alert',
            'body': '{}'.format(course.id),
            'html': None,
        }

        with LogCapture(logger_name) as logger, \
                patch(email_sender) as mock_send_email:
            call_command(self.command)
            logger.check_present(
                (
                    logger_name,
                    'INFO',
                    'Sent Expired Courses alert email to mobile team.'
                )
            )
            assert mock_send_email.call_count == 1
            mock_send_email.assert_called_with(mock_mobile_team_mail, mock_email_body)

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    def test_send_mail_to_mobile_team_with_no_email(self, mock_publish_to_lms, mock_course_run, mock_course_detail):
        logger_name = 'ecommerce.extensions.iap.management.commands.batch_update_mobile_seats'
        email_sender = 'ecommerce.extensions.communication.utils.Dispatcher.dispatch_direct_messages'
        iap_configs = IAPProcessorConfiguration.get_solo()
        iap_configs.mobile_team_email = ""
        iap_configs.save()
        course = self._create_course_and_seats(create_mobile_seats=True, expired_in_past=True)

        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = {'course': course.id}
        mock_course_detail.return_value = {'course_run_keys': []}

        with LogCapture(logger_name) as logger, \
                patch(email_sender) as mock_send_email:
            call_command(self.command)
            msg = "Couldn't mail mobile team for expired courses with SKUS. " \
                  "No email was specified for mobile team in configurations"
            logger.check_present(
                (
                    logger_name,
                    'INFO',
                    msg
                )
            )
            assert mock_send_email.call_count == 0
