import datetime
from unittest import mock
from uuid import uuid4

from django.test import RequestFactory
from oscar.core.loading import get_model
from testfixtures import LogCapture

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.extensions.api.serializers import (
    CouponCodeAssignmentSerializer,
    CouponCodeRemindSerializer,
    CouponCodeRevokeSerializer,
    OrderSerializer
)
from ecommerce.extensions.test import factories
from ecommerce.tests.testcases import TestCase

OfferAssignment = get_model('offer', 'OfferAssignment')
Voucher = get_model('voucher', 'Voucher')


class OrderSerializerTests(TestCase):
    """ Test for order serializers. """
    LOGGER_NAME = 'ecommerce.extensions.api.serializers'

    def setUp(self):
        super(OrderSerializerTests, self).setUp()
        self.user = self.create_user()

    @mock.patch('ecommerce.extensions.checkout.views.ReceiptResponseView.get_order_dashboard_url')
    def test_get_dashboard_url(self, mock_receipt_dashboard_url):
        mock_receipt_dashboard_url.side_effect = ValueError()
        order = factories.create_order(site=self.site, user=self.user)
        serializer = OrderSerializer(order, context={'request': RequestFactory(SERVER_NAME=self.site.domain).get('/')})

        expected = [
            (
                self.LOGGER_NAME,
                'ERROR',
                'Failed to retrieve get_dashboard_url for [{}]'.format(order)
            ),
        ]

        with LogCapture(self.LOGGER_NAME) as logger:
            serializer.get_dashboard_url(order)
            self.assertTrue(mock_receipt_dashboard_url.called)
            logger.check_present(*expected)

    @mock.patch('ecommerce.extensions.checkout.views.ReceiptResponseView.order_contains_credit_seat')
    def test_get_contains_credit_seat(self, mock_contains_credit_seat):
        mock_contains_credit_seat.side_effect = ValueError()
        order = factories.create_order(site=self.site, user=self.user)
        serializer = OrderSerializer(order, context={'request': RequestFactory(SERVER_NAME=self.site.domain).get('/')})

        expected = [
            (
                self.LOGGER_NAME,
                'ERROR',
                'Failed to retrieve get_contains_credit_seat for [{}]'.format(order)
            ),
        ]

        with LogCapture(self.LOGGER_NAME) as logger:
            serializer.get_contains_credit_seat(order)
            self.assertTrue(mock_contains_credit_seat)
            logger.check_present(*expected)

    @mock.patch('ecommerce.extensions.checkout.views.ReceiptResponseView.get_payment_method')
    def test_get_payment_method(self, mock_receipt_payment_method):
        mock_receipt_payment_method.side_effect = ValueError()
        order = factories.create_order(site=self.site, user=self.user)
        serializer = OrderSerializer(order, context={'request': RequestFactory(SERVER_NAME=self.site.domain).get('/')})

        expected = [
            (
                self.LOGGER_NAME,
                'ERROR',
                'Failed to retrieve get_payment_method for order [{}]'.format(order)
            ),
        ]

        with LogCapture(self.LOGGER_NAME) as logger:
            serializer.get_payment_method(order)
            self.assertTrue(mock_receipt_payment_method)
            logger.check_present(*expected)

    @mock.patch('ecommerce.extensions.checkout.views.ReceiptResponseView.add_message_if_enterprise_user')
    def test_get_enterprise_customer_info(self, mock_learner_portal_url):
        mock_learner_portal_url.side_effect = ValueError()
        order = factories.create_order(site=self.site, user=self.user)
        serializer = OrderSerializer(order, context={'request': RequestFactory(SERVER_NAME=self.site.domain).get('/')})

        expected = [
            (
                self.LOGGER_NAME,
                'ERROR',
                'Failed to retrieve enterprise_customer_info for order [{}]'.format(order)
            ),
        ]

        with LogCapture(self.LOGGER_NAME) as logger:
            serializer.get_enterprise_customer_info(order)
            self.assertTrue(mock_learner_portal_url)
            logger.check_present(*expected)


class CouponCodeSerializerTests(CouponMixin, TestCase):
    """ Test for coupon code serializers. """
    LOGGER_NAME = 'ecommerce.extensions.api.serializers'
    TEMPLATE = 'Text {PARAM} is fun'
    SUBJECT = 'Subject '
    GREETING = 'Hello '
    CLOSING = ' Bye'
    BASE_ENTERPRISE_URL = 'https://bears.party'
    SENDER_ALIAS = 'edX Support Team'
    REPLY_TO = 'edx@example.com'
    ATTACHMENTS = [{'name': 'abc.png', 'url': 'https://www.example.com'},
                   {'name': 'def.png', 'url': 'https://www.example.com'}]

    def setUp(self):
        super(CouponCodeSerializerTests, self).setUp()

        self.coupon = self.create_coupon(
            benefit_value=25,
            code='serializeCouponTest',
            enterprise_customer='af4b351f-5f1c-4fc3-af41-48bb38fcb161',
            catalog=None,
            enterprise_customer_catalog='8212a8d8-c6b1-4023-8754-4d687c43d72f',
            end_datetime=(datetime.datetime.now() + datetime.timedelta(days=10))
        )
        self.code = self.coupon.attr.coupon_vouchers.vouchers.first().code
        self.email = 'serializeCoupon@test.org'
        self.data = {'code': self.code, 'user': {'email': self.email}}
        self.code_assignment_serializer_data = {
            'codes': [self.code],
            'users': [
                {
                    'email': self.email,
                    'lms_user_id': 1,
                    'username': 'username1',
                },
                {
                    'email': 'serializeCoupon2@test.org',
                    'lms_user_id': 2,
                    'username': 'username2',
                },
            ]
        }
        self.offer_assignments = factories.EnterpriseOfferFactory.create_batch(1)
        self.offer_assignment = OfferAssignment.objects.create(
            offer=self.offer_assignments[0],
            code=self.code,
            user_email=self.email,
        )

    @mock.patch('ecommerce.extensions.api.serializers.send_assigned_offer_email')
    def test_send_assigned_offer_email_args(self, mock_assign_email):
        """ Test that the code_expiration_date passed is equal to coupon batch end date """
        serializer = CouponCodeAssignmentSerializer(data=self.code_assignment_serializer_data,
                                                    context={'coupon': self.coupon})
        serializer._trigger_email_sending_task(  # pylint: disable=protected-access
            subject=self.SUBJECT,
            greeting=self.GREETING,
            closing=self.CLOSING,
            assigned_offer=self.offer_assignment,
            voucher_usage_type=Voucher.MULTI_USE_PER_CUSTOMER,
            sender_alias=self.SENDER_ALIAS,
            reply_to=self.REPLY_TO,
            attachments=self.ATTACHMENTS,
        )
        expected_expiration_date = self.coupon.attr.coupon_vouchers.vouchers.first().end_datetime

        assert mock_assign_email.call_count == 1
        assign_email_args = mock_assign_email.call_args[1]
        assert assign_email_args['subject'] == self.SUBJECT
        assert assign_email_args['greeting'] == self.GREETING
        assert assign_email_args['closing'] == self.CLOSING
        assert assign_email_args['learner_email'] == self.offer_assignment.user_email
        assert assign_email_args['offer_assignment_id'] == self.offer_assignment.id
        assert assign_email_args['code'] == self.offer_assignment.code
        assert assign_email_args['code_expiration_date'] == expected_expiration_date.strftime('%d %B, %Y %H:%M %Z')
        assert assign_email_args['base_enterprise_url'] == ''
        assert assign_email_args['sender_alias'] == self.SENDER_ALIAS
        assert assign_email_args['reply_to'] == self.REPLY_TO
        assert assign_email_args['attachments'] == self.ATTACHMENTS

    @mock.patch('ecommerce.extensions.api.serializers.send_assigned_offer_email')
    def test_send_assigned_offer_email_args_with_enterprise_url(self, mock_assign_email):
        """ Test that the code_expiration_date passed is equal to coupon batch end date """
        serializer = CouponCodeAssignmentSerializer(data=self.code_assignment_serializer_data,
                                                    context={'coupon': self.coupon})
        serializer._trigger_email_sending_task(  # pylint: disable=protected-access
            subject=self.SUBJECT,
            greeting=self.GREETING,
            closing=self.CLOSING,
            assigned_offer=self.offer_assignment,
            voucher_usage_type=Voucher.MULTI_USE_PER_CUSTOMER,
            sender_alias=self.SENDER_ALIAS,
            reply_to=self.REPLY_TO,
            attachments=self.ATTACHMENTS,
            base_enterprise_url=self.BASE_ENTERPRISE_URL,
        )
        expected_expiration_date = self.coupon.attr.coupon_vouchers.vouchers.first().end_datetime

        assert mock_assign_email.call_count == 1
        assign_email_args = mock_assign_email.call_args[1]
        assert assign_email_args['subject'] == self.SUBJECT
        assert assign_email_args['greeting'] == self.GREETING
        assert assign_email_args['closing'] == self.CLOSING
        assert assign_email_args['learner_email'] == self.offer_assignment.user_email
        assert assign_email_args['offer_assignment_id'] == self.offer_assignment.id
        assert assign_email_args['code'] == self.offer_assignment.code
        assert assign_email_args['code_expiration_date'] == expected_expiration_date.strftime('%d %B, %Y %H:%M %Z')
        assert assign_email_args['base_enterprise_url'] == self.BASE_ENTERPRISE_URL
        assert assign_email_args['sender_alias'] == self.SENDER_ALIAS
        assert assign_email_args['reply_to'] == self.REPLY_TO
        assert assign_email_args['attachments'] == self.ATTACHMENTS

    @mock.patch('ecommerce.extensions.api.serializers.send_assigned_offer_reminder_email')
    def test_send_assigned_offer_reminder_email_args(self, mock_remind_email):
        """ Test that the code_expiration_date passed is equal to coupon batch end date """
        serializer = CouponCodeRemindSerializer(data=self.data, context={'coupon': self.coupon})
        serializer._trigger_email_sending_task(  # pylint: disable=protected-access
            subject=self.SUBJECT,
            greeting=self.GREETING,
            closing=self.CLOSING,
            assigned_offer=self.offer_assignment,
            redeemed_offer_count=3,
            total_offer_count=5,
            sender_alias=self.SENDER_ALIAS,
            reply_to=self.REPLY_TO,
            attachments=self.ATTACHMENTS,
        )
        expected_expiration_date = self.coupon.attr.coupon_vouchers.vouchers.first().end_datetime
        mock_remind_email.assert_called_with(
            subject=self.SUBJECT,
            greeting=self.GREETING,
            closing=self.CLOSING,
            learner_email=self.offer_assignment.user_email,
            code=self.offer_assignment.code,
            redeemed_offer_count=mock.ANY,
            total_offer_count=mock.ANY,
            code_expiration_date=expected_expiration_date.strftime('%d %B, %Y %H:%M %Z'),
            sender_alias=self.SENDER_ALIAS,
            reply_to=self.REPLY_TO,
            attachments=self.ATTACHMENTS,
            base_enterprise_url=''
        )

    @mock.patch('ecommerce.extensions.api.serializers.send_assigned_offer_reminder_email')
    def test_send_assigned_offer_reminder_email_args_with_base_url(self, mock_remind_email):
        """ Test that the code_expiration_date passed is equal to coupon batch end date """
        serializer = CouponCodeRemindSerializer(data=self.data, context={'coupon': self.coupon})
        serializer._trigger_email_sending_task(  # pylint: disable=protected-access
            subject=self.SUBJECT,
            greeting=self.GREETING,
            closing=self.CLOSING,
            assigned_offer=self.offer_assignment,
            redeemed_offer_count=3,
            total_offer_count=5,
            sender_alias=self.SENDER_ALIAS,
            reply_to=self.REPLY_TO,
            attachments=self.ATTACHMENTS,
            base_enterprise_url=self.BASE_ENTERPRISE_URL
        )
        expected_expiration_date = self.coupon.attr.coupon_vouchers.vouchers.first().end_datetime
        mock_remind_email.assert_called_with(
            subject=self.SUBJECT,
            greeting=self.GREETING,
            closing=self.CLOSING,
            learner_email=self.offer_assignment.user_email,
            code=self.offer_assignment.code,
            redeemed_offer_count=mock.ANY,
            total_offer_count=mock.ANY,
            code_expiration_date=expected_expiration_date.strftime('%d %B, %Y %H:%M %Z'),
            sender_alias=self.SENDER_ALIAS,
            reply_to=self.REPLY_TO,
            attachments=self.ATTACHMENTS,
            base_enterprise_url=self.BASE_ENTERPRISE_URL,
        )

    @mock.patch('ecommerce.extensions.api.serializers.send_assigned_offer_email')
    def test_send_assignment_email_error(self, mock_email):
        """ Test that we log an appropriate message if the code assignment email cannot be sent. """
        mock_email.side_effect = Exception('Ignore me - assignment')
        serializer = CouponCodeAssignmentSerializer(data=self.code_assignment_serializer_data,
                                                    context={'coupon': self.coupon})
        expected = [
            (
                self.LOGGER_NAME,
                'ERROR',
                '[Offer Assignment] Email for offer_assignment_id: {} with subject \'{}\', greeting \'{}\' closing '
                '\'{}\' and attachments {}, raised exception: {}'.format(
                    self.offer_assignment.id,
                    self.SUBJECT,
                    self.GREETING,
                    self.CLOSING,
                    self.ATTACHMENTS,
                    repr(Exception('Ignore me - assignment'))
                )
            ),
        ]

        with LogCapture(self.LOGGER_NAME) as log:
            serializer._trigger_email_sending_task(  # pylint: disable=protected-access
                subject=self.SUBJECT,
                greeting=self.GREETING,
                closing=self.CLOSING,
                assigned_offer=self.offer_assignment,
                voucher_usage_type=Voucher.MULTI_USE_PER_CUSTOMER,
                sender_alias=self.SENDER_ALIAS,
                reply_to=self.REPLY_TO,
                attachments=self.ATTACHMENTS,
            )
            log.check_present(*expected)

    @mock.patch('ecommerce.extensions.api.serializers.send_assigned_offer_reminder_email')
    def test_send_reminder_email_error(self, mock_email):
        """ Test that we log an appropriate message if the code reminder email cannot be sent. """
        mock_email.side_effect = Exception('Ignore me - reminder')
        serializer = CouponCodeRemindSerializer(data=self.data, context={'coupon': self.coupon})
        expected = [
            (
                self.LOGGER_NAME,
                'ERROR',
                '[Offer Reminder] Email for offer_assignment_id: {} with subject \'{}\', greeting \'{}\' '
                'closing \'{}\' attachments {}, and base_enterprise_url \'{}\' raised exception: {}'.format(
                    self.offer_assignment.id,
                    self.SUBJECT,
                    self.GREETING,
                    self.CLOSING,
                    self.ATTACHMENTS,
                    self.BASE_ENTERPRISE_URL,
                    repr(Exception('Ignore me - reminder'))
                )
            ),
        ]

        with self.assertRaises(Exception):
            with LogCapture(self.LOGGER_NAME) as log:
                serializer._trigger_email_sending_task(  # pylint: disable=protected-access
                    subject=self.SUBJECT,
                    greeting=self.GREETING,
                    closing=self.CLOSING,
                    assigned_offer=self.offer_assignment,
                    redeemed_offer_count=3,
                    total_offer_count=5,
                    sender_alias=self.SENDER_ALIAS,
                    reply_to=self.REPLY_TO,
                    attachments=self.ATTACHMENTS,
                    base_enterprise_url=self.BASE_ENTERPRISE_URL,
                )
        log.check_present(*expected)

    @mock.patch('ecommerce.extensions.api.serializers.send_revoked_offer_email')
    def test_send_revoke_email_args_with_base_url(self, mock_revoke_email):
        """ Test that revoke email is passed correct enterprise_base_url """
        context = {
            'coupon': self.coupon,
            'subject': self.SUBJECT,
            'greeting': self.GREETING,
            'closing': self.CLOSING,
            'files': self.ATTACHMENTS,
            'base_enterprise_url': self.BASE_ENTERPRISE_URL,
        }
        validated_data = {
            'code': self.code,
            'user': {'email': self.email},
            'offer_assignments': self.offer_assignments,
            'sender_id': None,
            'template': None,
            'enterprise_customer_uuid': uuid4()
        }
        serializer = CouponCodeRevokeSerializer(data=self.data, context=context)
        serializer.create(validated_data=validated_data)
        mock_revoke_email.assert_called_with(
            subject=self.SUBJECT,
            greeting=self.GREETING,
            closing=self.CLOSING,
            learner_email=self.email,
            code=self.code,
            sender_alias=self.SENDER_ALIAS,
            reply_to='',
            base_enterprise_url=self.BASE_ENTERPRISE_URL,
            attachments=self.ATTACHMENTS
        )

    def test_send_revocation_email_error_no_greeting(self):
        """ Test that we log an appropriate message if the code revocation email cannot be sent. """
        serializer = CouponCodeRevokeSerializer(data=self.data, context={'coupon': self.coupon})

        expected = [
            (   # pylint: disable=too-many-format-args
                self.LOGGER_NAME,
                'ERROR',
                '[Offer Revocation] Encountered error when revoking code {} for user {} with subject {}, '
                'greeting {} closing {} base_enterprise_url \'{}\' and files []'.format(
                    None,
                    None,
                    None,
                    None,
                    None,
                    '',
                )
            ),
        ]
        with LogCapture(self.LOGGER_NAME) as log:
            serializer.create(
                validated_data={
                    'sender_id': None,
                    'template': None,
                    'user': {'email': None},
                    'enterprise_customer_uuid': uuid4()
                }
            )
            log.check_present(*expected)

    @mock.patch('ecommerce.extensions.api.serializers.send_revoked_offer_email')
    def test_send_revocation_email_error(self, mock_email):
        """ Test that we log an appropriate message if the code revocation email cannot be sent. """
        mock_email.side_effect = Exception('Ignore me - revocation')
        validated_data = {
            'code': self.code,
            'user': {'email': self.email},
            'offer_assignments': self.offer_assignments,
            'sender_id': None,
            'template': None,
            'enterprise_customer_uuid': uuid4()
        }
        context = {
            'coupon': self.coupon,
            'subject': self.SUBJECT,
            'greeting': self.GREETING,
            'closing': self.CLOSING,
            'base_enterprise_url': self.BASE_ENTERPRISE_URL,
            'files': self.ATTACHMENTS
        }
        serializer = CouponCodeRevokeSerializer(data=self.data, context=context)

        expected = [
            (
                self.LOGGER_NAME,
                'ERROR',
                '[Offer Revocation] Encountered error when revoking code {} for user {} with subject \'{}\', '
                'greeting \'{}\' closing \'{}\' base_enterprise_url \'{}\' and files {}'.format(
                    self.code,
                    self.email,
                    self.SUBJECT,
                    self.GREETING,
                    self.CLOSING,
                    self.BASE_ENTERPRISE_URL,
                    self.ATTACHMENTS,
                )
            ),
        ]
        with LogCapture(self.LOGGER_NAME) as log:
            serializer.create(validated_data=validated_data)
            log.check_present(*expected)
