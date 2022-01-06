# -*- coding: utf-8 -*-

import botocore
import mock
from django.conf import settings

from ecommerce.extensions.api.v2.utils import (
    SMTPException,
    send_new_codes_notification_email,
    upload_files_for_enterprise_coupons
)
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

    def mock_make_api_call(self, operation_name, kwarg):
        orig = botocore.client.BaseClient._make_api_call  # pylint: disable=protected-access
        put_object_response = {
            "ResponseMetadata": {
                "RequestId": "5994D680BF127CE3",
                "HTTPStatusCode": 200,
                "RetryAttempts": 1,
            },
            "ETag": '"6299528715bad0e3510d1e4c4952ee7e"',
        }
        if operation_name == 'GetBucketLocation':  # pylint: disable=no-else-return
            return {'LocationConstraint': settings.ENTERPRISE_EMAIL_FILE_ATTACHMENTS_BUCKET_LOCATION}
        elif operation_name == 'PutObject':
            return put_object_response
        else:
            return orig(self, operation_name, kwarg)

    def test_files_uploads_to_s3(self):
        """ verify that files are uploaded to s3 correctly"""
        un_uploaded_files = [{'name': 'abc.png', 'size': 123, 'contents': '1,2,3', 'type': 'image/png'},
                             {'name': 'def.png', 'size': 456, 'contents': '1,2,3', 'type': 'image/png'}]
        with mock.patch('botocore.client.BaseClient._make_api_call', new=self.mock_make_api_call):
            res = upload_files_for_enterprise_coupons(un_uploaded_files)
            assert res[0]['size'] == un_uploaded_files[0]['size']
            assert res[1]['size'] == un_uploaded_files[1]['size']
            assert res[0]['url'].startswith(
                f'https://.s3.{settings.ENTERPRISE_EMAIL_FILE_ATTACHMENTS_BUCKET_LOCATION}.amazonaws.com')
            assert res[1]['url'].startswith(
                f'https://.s3.{settings.ENTERPRISE_EMAIL_FILE_ATTACHMENTS_BUCKET_LOCATION}.amazonaws.com')
            assert res[0]['url'].endswith('abcpng')
            assert res[1]['url'].endswith('defpng')

    def test_file_uploads_to_s3_with_no_bucket_name(self):
        """ Verify that exception log message is correct on file uploads with no bucket name. """
        un_uploaded_files = [{'name': 'abc.png', 'size': 123, 'contents': '1,2,3', 'type': 'image/png'},
                             {'name': 'def.png', 'size': 456, 'contents': '1,2,3', 'type': 'image/png'}]
        with mock.patch('ecommerce.extensions.api.v2.utils.logger') as mock_logger:
            ret = upload_files_for_enterprise_coupons(un_uploaded_files)
            assert '[upload_files_for_enterprise_coupons] Raised an error while uploading the files,Message' \
                   in mock_logger.exception.call_args[0][0]
            assert 'Invalid bucket name ' in str(mock_logger.exception.call_args[0][1])
            assert ret == []  # pylint: disable=use-implicit-booleaness-not-comparison
