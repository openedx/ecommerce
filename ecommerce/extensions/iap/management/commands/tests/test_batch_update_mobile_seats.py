"""Tests for the batch_update_mobile_seats command"""
from unittest.mock import patch

from django.core.management import call_command
from testfixtures import LogCapture

from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.models import Product
from ecommerce.extensions.iap.management.commands.batch_update_mobile_seats import Command as mobile_seats_command
from ecommerce.extensions.iap.management.commands.tests.testutils import BaseIAPManagementCommandTests
from ecommerce.extensions.iap.models import IAPProcessorConfiguration


class BatchUpdateMobileSeatsTests(BaseIAPManagementCommandTests):
    """
    Tests for the batch_update_mobile_seats command.
    """
    def setUp(self):
        super().setUp()
        self.command = 'batch_update_mobile_seats'

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.Command._create_ios_product')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_mobile_seat_for_new_course_run_created(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail, mock_create_ios_product):
        """Test that the command creates mobile seats for new course run."""
        course_with_mobile_seat = self.create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        course_run_without_mobile_seat = self.create_course_and_seats()
        course_run_return_value = {'course': course_with_mobile_seat.id}
        course_detail_return_value = {'course_run_keys': [course_run_without_mobile_seat.id]}

        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = course_run_return_value
        mock_course_detail.return_value = course_detail_return_value
        mock_create_ios_product.return_value = None

        call_command(self.command)
        actual_mobile_seats = Product.objects.filter(
            course=course_run_without_mobile_seat,
            stockrecords__partner_sku__icontains='mobile'
        )
        expected_mobile_seats_count = 2
        self.assertTrue(actual_mobile_seats.exists())
        self.assertEqual(actual_mobile_seats.count(), expected_mobile_seats_count)

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.Command._create_ios_product')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_extra_seats_not_created(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail, mock_create_ios_product):
        """Test the case where mobile seats are already created for course run."""
        course_with_mobile_seat = self.create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        course_run_with_mobile_seat = self.create_course_and_seats(create_mobile_seats=True)
        course_run_return_value = {'course': course_with_mobile_seat.id}
        course_detail_return_value = {'course_run_keys': [course_run_with_mobile_seat.id]}

        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = course_run_return_value
        mock_course_detail.return_value = course_detail_return_value
        mock_create_ios_product.return_value = None

        call_command(self.command)
        actual_mobile_seats = Product.objects.filter(
            course=course_run_with_mobile_seat,
            stockrecords__partner_sku__icontains='mobile'
        )
        expected_mobile_seats_count = 2
        self.assertTrue(actual_mobile_seats.exists())
        self.assertEqual(actual_mobile_seats.count(), expected_mobile_seats_count)

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.create_child_products_for_mobile')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.Command._create_ios_product')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_no_mobile_products_returned(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail, mock_create_ios_product,
            mock_create_child_products):
        """Test the case where mobile seats are already created for course run."""
        course_with_mobile_seat = self.create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        course_run_with_mobile_seat = self.create_course_and_seats(create_mobile_seats=False)
        course_run_return_value = {'course': course_with_mobile_seat.id}
        course_detail_return_value = {'course_run_keys': [course_run_with_mobile_seat.id]}

        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = course_run_return_value
        mock_course_detail.return_value = course_detail_return_value
        mock_create_ios_product.return_value = None
        mock_create_child_products.return_value = None

        call_command(self.command)
        actual_mobile_seats = Product.objects.filter(
            course=course_run_with_mobile_seat,
            stockrecords__partner_sku__icontains='mobile'
        )
        expected_mobile_seats_count = 0
        self.assertFalse(actual_mobile_seats.exists())
        self.assertEqual(actual_mobile_seats.count(), expected_mobile_seats_count)

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.Command._create_ios_product')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_no_response_from_discovery_for_course_run_api(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail, mock_create_ios_product):
        """Test that the command handles exceptions if no response returned from Discovery for course run API."""
        course_with_mobile_seat = self.create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        course_run_without_mobile_seat = self.create_course_and_seats()
        course_run_return_value = None
        course_detail_return_value = {'course_run_keys': [course_run_without_mobile_seat.id]}

        logger_name = 'ecommerce.extensions.iap.management.commands.batch_update_mobile_seats'
        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = course_run_return_value
        mock_course_detail.return_value = course_detail_return_value
        mock_create_ios_product.return_value = None

        with LogCapture(logger_name) as logger:
            call_command(self.command)
            msg = "Error while fetching parent course for {} from discovery".format(course_with_mobile_seat.id)
            logger.check_present((logger_name, 'ERROR', msg))

        actual_mobile_seats = Product.objects.filter(
            course=course_run_without_mobile_seat,
            stockrecords__partner_sku__icontains='mobile'
        )
        self.assertFalse(actual_mobile_seats.exists())

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.Command._create_ios_product')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_no_response_from_discovery_for_course_detail_api(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail, mock_create_ios_product):
        """Test that the command handles exceptions if no response returned from Discovery for course detail API."""
        course_with_mobile_seat = self.create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        course_run_without_mobile_seat = self.create_course_and_seats()
        course_run_return_value = {'course': course_with_mobile_seat.id}

        logger_name = 'ecommerce.extensions.iap.management.commands.batch_update_mobile_seats'
        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = course_run_return_value
        mock_course_detail.return_value = None
        mock_create_ios_product.return_value = None

        with LogCapture(logger_name) as logger:
            call_command(self.command)
            msg = "Error while fetching course runs for {} from discovery".format(course_with_mobile_seat.id)
            logger.check_present((logger_name, 'ERROR', msg))

        actual_mobile_seats = Product.objects.filter(
            course=course_run_without_mobile_seat,
            stockrecords__partner_sku__icontains='mobile'
        )
        self.assertFalse(actual_mobile_seats.exists())

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.create_ios_product')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_error_in_creating_ios_products(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail, mock_create_ios_product):
        """Test the case where mobile seats are already created for course run."""
        course_with_mobile_seat = self.create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        course_run_with_mobile_seat = self.create_course_and_seats(create_mobile_seats=False)
        course_run_return_value = {'course': course_with_mobile_seat.id}
        course_detail_return_value = {'course_run_keys': [course_run_with_mobile_seat.id]}

        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = course_run_return_value
        mock_course_detail.return_value = course_detail_return_value
        mock_create_ios_product.return_value = "Error creating ios product"

        call_command(self.command)
        actual_mobile_seats = Product.objects.filter(
            course=course_run_with_mobile_seat,
            stockrecords__partner_sku__icontains='mobile'
        )
        expected_mobile_seats_count = 2
        self.assertTrue(actual_mobile_seats.exists())
        self.assertEqual(actual_mobile_seats.count(), expected_mobile_seats_count)

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.Command._create_ios_product')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    @patch.object(mobile_seats_command, '_send_email_about_expired_courses')
    def test_command_arguments_are_processed(
            self, mock_email, mock_publish_to_lms, mock_course_run, mock_course_detail, mock_create_ios_product):
        course_with_mobile_seat = self.create_course_and_seats(create_mobile_seats=True, expired_in_past=True)
        mock_email.return_value = None
        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = {'course': course_with_mobile_seat.id}
        mock_course_detail.return_value = {'course_run_keys': []}
        mock_create_ios_product.return_value = None

        call_command(self.command, batch_size=1, sleep_time=1)
        assert mock_email.call_count == 1

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.Command._create_ios_product')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.Command._get_email_contents')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    def test_send_mail_to_mobile_team(self, mock_publish_to_lms, mock_course_run, mock_course_detail,
                                      mock_get_email_contents, mock_create_ios_product):
        logger_name = 'ecommerce.extensions.iap.management.commands.batch_update_mobile_seats'
        email_sender = 'ecommerce.extensions.communication.utils.Dispatcher.dispatch_direct_messages'
        mock_mobile_team_mail = 'abc@example.com'
        iap_configs = IAPProcessorConfiguration.get_solo()
        iap_configs.mobile_team_email = mock_mobile_team_mail
        iap_configs.save()
        course = self.create_course_and_seats(create_mobile_seats=True, expired_in_past=True)

        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = {'course': course.id}
        mock_course_detail.return_value = {'course_run_keys': []}
        mock_get_email_contents.return_value = "mock_email_contents"
        mock_create_ios_product.return_value = None

        mock_email_body = {
            'subject': 'Expired Courses with mobile SKUS alert',
            'body': 'mock_email_contents',
            'html': None,
        }

        with LogCapture(logger_name) as logger,\
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

    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.Command._create_ios_product')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.Command._get_email_contents')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_detail')
    @patch('ecommerce.extensions.iap.management.commands.batch_update_mobile_seats.get_course_run_detail')
    @patch.object(Course, 'publish_to_lms')
    def test_send_mail_to_mobile_team_with_no_email(self, mock_publish_to_lms, mock_course_run, mock_course_detail,
                                                    mock_get_email_contents, mock_create_ios_product):
        logger_name = 'ecommerce.extensions.iap.management.commands.batch_update_mobile_seats'
        email_sender = 'ecommerce.extensions.communication.utils.Dispatcher.dispatch_direct_messages'
        iap_configs = IAPProcessorConfiguration.get_solo()
        iap_configs.mobile_team_email = ""
        iap_configs.save()
        course = self.create_course_and_seats(create_mobile_seats=True, expired_in_past=True)

        mock_publish_to_lms.return_value = None
        mock_course_run.return_value = {'course': course.id}
        mock_course_detail.return_value = {'course_run_keys': []}
        mock_get_email_contents.return_value = "mock_email_contents"
        mock_create_ios_product.return_value = None

        with LogCapture(logger_name) as logger, \
                patch(email_sender) as mock_send_email:
            call_command(self.command)
            msg = "Couldn't mail mobile team for expired courses with SKUS. " \
                  "No email was specified for mobile team in configurations.\n " \
                  "Email contents: mock_email_contents"
            logger.check_present(
                (
                    logger_name,
                    'INFO',
                    msg
                )
            )
            assert mock_send_email.call_count == 0

    def test_no_expired_courses(self):
        logger_name = 'ecommerce.extensions.iap.management.commands.batch_update_mobile_seats'
        email_sender = 'ecommerce.extensions.communication.utils.Dispatcher.dispatch_direct_messages'
        mock_mobile_team_mail = 'abc@example.com'
        iap_configs = IAPProcessorConfiguration.get_solo()
        iap_configs.mobile_team_email = mock_mobile_team_mail
        iap_configs.save()
        self.create_course_and_seats(create_mobile_seats=True, expired_in_past=False)

        expected_body = "\nExpired Courses:\n"
        expected_body += "\n\nNew course runs processed:\n"
        expected_body += "\n\nFailed course runs:\n"
        expected_body += "\n\nSeats created:\n"
        expected_body += "\n\nFailed iOS products:\n"

        mock_email_body = {
            'subject': 'Expired Courses with mobile SKUS alert',
            'body': expected_body,
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
            mock_send_email.assert_called_with(mock_mobile_team_mail, mock_email_body)
