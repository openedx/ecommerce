# -*- coding: utf-8 -*-


import mock

from ecommerce.extensions.api.v2.utils import SMTPException, send_new_codes_notification_email
from ecommerce.tests.testcases import TestCase


class ViewUtilsTests(TestCase):
    """
    Tests for view utils
    """

    def setUp(self):
        self.email_address = 'batman@gotham.comics'
        self.enterprise_id = '6ae013d4-c5c4-474d-8da9-0e559b2448e2'
        self.coupon_id = '777'

        get_enterprise_customer_patcher = mock.patch('ecommerce.extensions.api.v2.utils.get_enterprise_customer')
        self.get_enterprise_customer_patcher = get_enterprise_customer_patcher.start()
        self.get_enterprise_customer_patcher.return_value = {
            'name': 'batman',
            'enterprise_customer_uuid': self.enterprise_id,
            'slug': 'batman',
        }
        self.addCleanup(get_enterprise_customer_patcher.stop)

    def test_send_new_codes_notification_email_info_log(self):
        """
        Verify that info log message is correct.
        """
        with mock.patch('ecommerce.extensions.api.v2.utils.logger') as mock_logger:
            send_new_codes_notification_email({}, self.email_address, self.enterprise_id, self.coupon_id)
            mock_logger.info.assert_called_with(
                'New codes email sent to enterprise customer [%s] for coupon [%s]',
                self.enterprise_id,
                self.coupon_id
            )

    def test_send_new_codes_notification_email_exception_log(self):
        """
        Verify that exception log message is correct.
        """
        with mock.patch('ecommerce.extensions.api.v2.utils.send_mail', side_effect=SMTPException):
            with mock.patch('ecommerce.extensions.api.v2.utils.logger') as mock_logger:
                send_new_codes_notification_email({}, self.email_address, self.enterprise_id, self.coupon_id)
                mock_logger.exception.assert_called_with(
                    'New codes email failed for enterprise customer [%s] for coupon [%s]',
                    self.enterprise_id,
                    self.coupon_id
                )
