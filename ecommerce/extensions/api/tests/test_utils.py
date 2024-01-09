import mock
from testfixtures import LogCapture

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.utils import send_mail_to_mobile_team_for_change_in_course
from ecommerce.extensions.iap.models import IAPProcessorConfiguration
from ecommerce.tests.testcases import TestCase


class UtilTests(TestCase):
    def setUp(self):
        super(UtilTests, self).setUp()
        self.course = CourseFactory(id='test/course/123', name='Test Course 123')
        seat = self.course.create_or_update_seat('verified', True, 60)
        second_seat = self.course.create_or_update_seat('verified', True, 70)
        self.mock_mobile_team_mail = 'abc@example.com'
        self.mock_email_body = {
            'subject': 'Course Change Alert for Test Course 123',
            'body': 'Course: Test Course 123, Sku: {}, Price: 70.00\n'
                    'Course: Test Course 123, Sku: {}, Price: 60.00'.format(
                        second_seat.stockrecords.all()[0].partner_sku,
                        seat.stockrecords.all()[0].partner_sku
                    )
        }

    def test_send_mail_to_mobile_team_with_no_email_specified(self):
        logger_name = 'ecommerce.extensions.api.utils'
        email_sender = 'ecommerce.extensions.communication.utils.Dispatcher.dispatch_direct_messages'
        msg_t = "Couldn't mail mobile team for change in {}. No email was specified for mobile team in configurations"
        msg = msg_t.format(self.course.name)
        with LogCapture(logger_name) as utils_logger, \
                mock.patch(email_sender) as mock_send_email:

            send_mail_to_mobile_team_for_change_in_course(self.course, self.course.seat_products.all())
            utils_logger.check_present(
                (
                    logger_name,
                    'INFO',
                    msg
                )
            )
            assert mock_send_email.call_count == 0

    def test_send_mail_to_mobile_team(self):
        logger_name = 'ecommerce.extensions.api.utils'
        email_sender = 'ecommerce.extensions.communication.utils.Dispatcher.dispatch_direct_messages'
        iap_configs = IAPProcessorConfiguration.get_solo()
        iap_configs.mobile_team_email = self.mock_mobile_team_mail
        iap_configs.save()
        with LogCapture(logger_name) as utils_logger, \
                mock.patch(email_sender) as mock_send_email:

            send_mail_to_mobile_team_for_change_in_course(self.course, self.course.seat_products.all())
            utils_logger.check_present(
                (
                    logger_name,
                    'INFO',
                    "Sent change in {} email to mobile team.".format(self.course.name)
                )
            )
            assert mock_send_email.call_count == 1
            mock_send_email.assert_called_with(self.mock_mobile_team_mail, self.mock_email_body)
