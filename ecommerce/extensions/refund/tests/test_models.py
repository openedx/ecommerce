

from decimal import Decimal

import ddt
import httpretty
import mock
from django.conf import settings
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_class, get_model
from testfixtures import LogCapture

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.core.url_utils import get_lms_enrollment_api_url
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.entitlements.utils import create_or_update_course_entitlement
from ecommerce.extensions.checkout.utils import format_currency, get_receipt_page_url
from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.extensions.refund import models
from ecommerce.extensions.refund.exceptions import InvalidStatus
from ecommerce.extensions.refund.status import REFUND, REFUND_LINE
from ecommerce.extensions.refund.tests.factories import RefundFactory, RefundLineFactory
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.extensions.test.factories import create_basket, create_order
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

PaymentEventType = get_model('order', 'PaymentEventType')
post_refund = get_class('refund.signals', 'post_refund')
Refund = get_model('refund', 'Refund')
Source = get_model('payment', 'Source')

LOGGER_NAME = 'ecommerce.extensions.analytics.utils'
REFUND_MODEL_LOGGER_NAME = 'ecommerce.extensions.refund.models'


class StatusTestsMixin:
    pipeline = None

    def _get_instance(self, **kwargs):
        """ Generate an instance of the model being tested. """
        raise NotImplementedError

    def test_available_statuses(self):
        """ Verify available_statuses() returns a list of statuses corresponding to the pipeline. """

        for status, allowed_transitions in self.pipeline.items():
            instance = self._get_instance(status=status)
            self.assertEqual(instance.available_statuses(), allowed_transitions)

    def test_set_status_invalid_status(self):
        """ Verify attempts to set the status to an invalid value raise an exception. """

        for status, valid_statuses in self.pipeline.items():
            instance = self._get_instance(status=status)

            all_statuses = list(self.pipeline.keys())
            invalid_statuses = set(all_statuses) - set(valid_statuses)

            for new_status in invalid_statuses:
                self.assertRaises(InvalidStatus, instance.set_status, new_status)
                self.assertEqual(instance.status, status,
                                 'Refund status should not be changed when attempting to set an invalid status.')

    def test_set_status_valid_status(self):
        """ Verify status is updated when attempting to transition to a valid status. """

        for status, valid_statuses in self.pipeline.items():
            for new_status in valid_statuses:
                instance = self._get_instance(status=status)
                instance.set_status(new_status)
                self.assertEqual(instance.status, new_status, 'Refund status was not updated!')


@ddt.ddt
class RefundTests(RefundTestMixin, StatusTestsMixin, TestCase):
    pipeline = settings.OSCAR_REFUND_STATUS_PIPELINE

    def _get_instance(self, **kwargs):
        return RefundFactory(**kwargs)

    def test_num_items(self):
        """ The method should return the total number of items being refunded. """
        refund = RefundFactory()
        self.assertEqual(refund.num_items, 1)

        RefundLineFactory(quantity=3, refund=refund)
        self.assertEqual(refund.num_items, 4)

    def test_all_statuses(self):
        """ Refund.all_statuses should return all possible statuses for a refund. """
        self.assertEqual(Refund.all_statuses(), list(self.pipeline.keys()))

    @ddt.data(False, True)
    def test_create_with_lines(self, multiple_lines):
        """
        Given an order and order lines that have not been refunded, Refund.create_with_lines
        should create a Refund with corresponding RefundLines.
        """
        order = self.create_order(user=UserFactory(), multiple_lines=multiple_lines)

        with LogCapture(LOGGER_NAME) as logger:
            refund = Refund.create_with_lines(order, list(order.lines.all()))

            self.assert_refund_creation_logged(logger, refund, order)

        self.assert_refund_matches_order(refund, order)

    def assert_refund_creation_logged(self, logger, refund, order):
        """
        Asserts that refund creation is logged.
        """
        logger.check_present(
            (
                LOGGER_NAME,
                'INFO',
                'refund_created: amount="{}", currency="{}", order_number="{}", '
                'refund_id="{}", user_id="{}"'.format(
                    refund.total_credit_excl_tax,
                    refund.currency,
                    order.number,
                    refund.id,
                    refund.user.id
                )
            )
        )

    @ddt.unpack
    @ddt.data(
        (REFUND.OPEN, False),
        (REFUND.PAYMENT_REFUND_ERROR, False),
        (REFUND.PAYMENT_REFUNDED, False),
        (REFUND.REVOCATION_ERROR, False),
        (REFUND.DENIED, True),
        (REFUND.COMPLETE, False),
    )
    def test_create_with_lines_with_existing_refund(self, refund_status, refund_created):
        """
        Refund.create_with_lines should not create RefundLines for order lines
        which have already been refunded.
        """
        order = self.create_order(user=UserFactory())
        line = order.lines.first()
        RefundLineFactory(order_line=line, status=refund_status)

        with LogCapture(LOGGER_NAME) as logger:
            refund = Refund.create_with_lines(order, [line])
            self.assertEqual(isinstance(refund, Refund), refund_created)
            if refund_created:
                self.assert_refund_creation_logged(logger, refund, order)

    @httpretty.activate
    @mock.patch('ecommerce.extensions.fulfillment.modules.EnrollmentFulfillmentModule.revoke_line')
    def test_zero_dollar_refund(self, mock_revoke_line):
        """
        Given an order and order lines which total $0 and are not refunded, Refund.create_with_lines
        should create and approve a Refund with corresponding RefundLines.
        """
        httpretty.register_uri(
            httpretty.POST,
            get_lms_enrollment_api_url(),
            status=200,
            body='{}',
            content_type='application/json'
        )

        order = self.create_order(user=UserFactory(), free=True)

        # Verify that the order totals $0.
        self.assertEqual(order.total_excl_tax, 0)

        with mock.patch.object(Refund, '_notify_purchaser') as mock_notify:
            refund = Refund.create_with_lines(order, list(order.lines.all()))

        # Verify that refund lines are not revoked.
        self.assertFalse(mock_revoke_line.called)

        # Verify that the refund has been successfully approved.
        self.assertEqual(refund.status, REFUND.COMPLETE)
        self.assertEqual({line.status for line in refund.lines.all()}, {REFUND_LINE.COMPLETE})

        # Verify no notification is sent to the purchaser
        self.assertFalse(mock_notify.called)

    @ddt.unpack
    @ddt.data(
        (REFUND.OPEN, True),
        (REFUND.PAYMENT_REFUND_ERROR, True),
        (REFUND.PAYMENT_REFUNDED, True),
        (REFUND.REVOCATION_ERROR, True),
        (REFUND.DENIED, False),
        (REFUND.COMPLETE, False),
    )
    def test_can_approve(self, status, expected):
        """ The method should return True if the Refund can be approved; otherwise, False. """
        refund = self._get_instance(status=status)
        self.assertEqual(refund.can_approve, expected)

    @ddt.unpack
    @ddt.data(
        (REFUND.OPEN, True),
        (REFUND.REVOCATION_ERROR, False),
        (REFUND.DENIED, False),
        (REFUND.COMPLETE, False),
    )
    def test_can_deny(self, status, expected):
        """ The method should return True if the Refund can be denied; otherwise, False. """
        refund = self._get_instance(status=status)
        self.assertEqual(refund.can_deny, expected)

    def assert_line_status(self, refund, status):
        for line in refund.lines.all():
            self.assertEqual(line.status, status)

    def assert_valid_payment_event_fields(self, payment_event, amount, payment_event_type, processor_name, reference):
        """ Ensures the given PaymentEvent's fields match the specified values. """
        self.assertEqual(payment_event.amount, amount)
        self.assertEqual(payment_event.event_type, payment_event_type)
        self.assertEqual(payment_event.reference, reference)
        self.assertEqual(payment_event.processor_name, processor_name)

    def test_approve(self):
        """
        If payment refund and fulfillment revocation succeed, the method should update the status of the Refund and
        RefundLine objects to Complete, and return True.
        """
        self.site.siteconfiguration.send_refund_notifications = True

        refund = self.create_refund()
        source = refund.order.sources.first()

        with LogCapture(LOGGER_NAME) as logger:
            with mock.patch.object(Refund, '_notify_purchaser', return_value=None) as mock_notify:
                self.approve(refund)

            logger.check_present(
                (
                    LOGGER_NAME,
                    'INFO',
                    'credit_issued: amount="{}", currency="{}", processor_name="{}", '
                    'refund_id="{}", user_id="{}"'.format(
                        refund.total_credit_excl_tax,
                        refund.currency,
                        source.source_type.name,
                        refund.id,
                        refund.user.id
                    )
                )
            )

        # Verify Source updated
        source = Source.objects.get(pk=source.pk)
        self.assertEqual(source.amount_refunded, refund.total_credit_excl_tax)

        # Verify PaymentEvent created
        paid_type = PaymentEventType.objects.get(code='refunded')
        payment_event = refund.order.payment_events.first()
        self.assert_valid_payment_event_fields(payment_event, refund.total_credit_excl_tax, paid_type,
                                               DummyProcessor.NAME, DummyProcessor.REFUND_TRANSACTION_ID)

        # Verify an attempt is made to send a notification
        mock_notify.assert_called_once_with()

        # Verify subsequent calls to approve an approved refund do not change the state
        refund.refresh_from_db()
        self.assertTrue(refund.approve())
        self.assertEqual(refund.status, REFUND.COMPLETE)

    def test_approve_payment_error(self):
        """
        If payment refund fails, the Refund status should be set to Payment Refund Error, and the RefundLine
        objects' statuses to Open.
        """
        refund = self._get_instance()

        with mock.patch.object(Refund, '_issue_credit', side_effect=PaymentError):
            self.assertFalse(refund.approve())
            self.assertEqual(refund.status, REFUND.PAYMENT_REFUND_ERROR)
            self.assert_line_status(refund, REFUND_LINE.OPEN)

    def test_approve_revocation_error(self):
        """
        If fulfillment revocation fails, Refund status should be set to Revocation Error and the RefundLine objects'
        statuses set to Revocation Error.
        """
        refund = self._get_instance()

        def revoke_fulfillment_for_refund(r):
            for line in r.lines.all():
                line.set_status(REFUND_LINE.REVOCATION_ERROR)

            return False

        with mock.patch.object(Refund, '_issue_credit', return_value=None):
            with mock.patch.object(models, 'revoke_fulfillment_for_refund') as mock_revoke:
                mock_revoke.side_effect = revoke_fulfillment_for_refund
                self.assertFalse(refund.approve())
                self.assertEqual(refund.status, REFUND.REVOCATION_ERROR)
                self.assert_line_status(refund, REFUND_LINE.REVOCATION_ERROR)

    def test_approve_wrong_state(self):
        """ The method should return False if the Refund cannot be approved. """
        status = REFUND.DENIED
        refund = self._get_instance(status=status)
        self.assertEqual(refund.status, status)
        self.assert_line_status(refund, REFUND_LINE.OPEN)

        self.assertFalse(refund.approve())
        self.assertEqual(refund.status, status)
        self.assert_line_status(refund, REFUND_LINE.OPEN)

    def test_deny(self):
        """
        The method should update the state of the Refund and related RefundLine objects, if the Refund can be
        denied, and return True.
        """
        refund = self._get_instance()
        self.assertEqual(refund.status, REFUND.OPEN)
        self.assert_line_status(refund, REFUND_LINE.OPEN)

        self.assertTrue(refund.deny())
        self.assertEqual(refund.status, REFUND.DENIED)
        self.assert_line_status(refund, REFUND_LINE.DENIED)

        # Verify subsequent calls to approve an approved refund do not change the state
        refund.refresh_from_db()
        self.assertTrue(refund.deny())
        self.assertEqual(refund.status, REFUND.DENIED)

    def test_deny_with_exception(self):
        """
        If denial of a line results in an exception being raised, the exception should be logged, and the method
        should return False.
        """
        # Create a Refund
        refund = self._get_instance()

        # Make RefundLine.deny() raise an exception
        with mock.patch('ecommerce.extensions.refund.models.RefundLine.deny', side_effect=Exception):
            with LogCapture(REFUND_MODEL_LOGGER_NAME) as logger:
                self.assertFalse(refund.deny())
                msg = 'Failed to deny RefundLine [{}].'.format(refund.lines.first().id)
                logger.check_present((REFUND_MODEL_LOGGER_NAME, 'ERROR', msg))

    @ddt.data(REFUND.REVOCATION_ERROR, REFUND.PAYMENT_REFUNDED, REFUND.PAYMENT_REFUND_ERROR, REFUND.COMPLETE)
    def test_deny_wrong_state(self, status):
        """ The method should return False if the Refund cannot be denied. """
        refund = self._get_instance(status=status)
        self.assertEqual(refund.status, status)
        self.assert_line_status(refund, REFUND_LINE.OPEN)

        self.assertFalse(refund.deny())
        self.assertEqual(refund.status, status)
        self.assert_line_status(refund, REFUND_LINE.OPEN)

    @mock.patch('ecommerce_worker.sailthru.v1.tasks.send_course_refund_email.delay')
    def test_notify_purchaser(self, mock_task):
        """ Verify the notification is scheduled if the site has notifications enabled
        and the refund is for a course seat.
        """
        site_configuration = self.site.siteconfiguration
        site_configuration.send_refund_notifications = True

        user = UserFactory()

        course = CourseFactory(partner=self.partner)
        price = Decimal(100.00)
        product = course.create_or_update_seat('verified', True, price)

        basket = create_basket(site=self.site, owner=user, empty=True)
        basket.add_product(product)

        order = create_order(basket=basket, user=user)
        order_url = get_receipt_page_url(site_configuration, order.number)

        refund = Refund.create_with_lines(order, order.lines.all())

        with LogCapture(REFUND_MODEL_LOGGER_NAME) as logger:
            refund._notify_purchaser()  # pylint: disable=protected-access

        msg = 'Course refund notification scheduled for Refund [{}].'.format(refund.id)
        logger.check_present(
            (REFUND_MODEL_LOGGER_NAME, 'INFO', msg)
        )

        amount = format_currency(order.currency, price)
        mock_task.assert_called_once_with(
            user.email, refund.id, amount, course.name, order.number, order_url, site_code=self.partner.short_code
        )

    @mock.patch('ecommerce_worker.sailthru.v1.tasks.send_course_refund_email.delay')
    def test_notify_purchaser_course_entielement(self, mock_task):
        """ Verify the notification is scheduled if the site has notifications enabled
        and the refund is for a course entitlement.
        """
        site_configuration = self.site.siteconfiguration
        site_configuration.send_refund_notifications = True

        user = UserFactory()

        course_entitlement = create_or_update_course_entitlement(
            'verified', 100, self.partner, '111-222-333-444', 'Course Entitlement')
        basket = create_basket(site=self.site, owner=user, empty=True)
        basket.add_product(course_entitlement, 1)

        order = create_order(number=1, basket=basket, user=user)
        order_url = get_receipt_page_url(site_configuration, order.number)

        refund = Refund.create_with_lines(order, order.lines.all())

        with LogCapture(REFUND_MODEL_LOGGER_NAME) as logger:
            refund._notify_purchaser()  # pylint: disable=protected-access

        msg = 'Course refund notification scheduled for Refund [{}].'.format(refund.id)
        logger.check_present(
            (REFUND_MODEL_LOGGER_NAME, 'INFO', msg)
        )

        amount = format_currency(order.currency, 100)
        mock_task.assert_called_once_with(
            user.email, refund.id, amount, course_entitlement.title, order.number,
            order_url, site_code=self.partner.short_code
        )

    @mock.patch('ecommerce_worker.sailthru.v1.tasks.send_course_refund_email.delay')
    def test_notify_purchaser_with_notifications_disabled(self, mock_task):
        """ Verify no notification is sent if the functionality is disabled for the site. """
        self.site.siteconfiguration.send_refund_notifications = False
        order = create_order(site=self.site)
        refund = self.create_refund(order=order)

        with LogCapture(REFUND_MODEL_LOGGER_NAME) as logger:
            refund._notify_purchaser()  # pylint: disable=protected-access

        msg = 'Refund notifications are disabled for Partner [{code}]. ' \
              'No notification will be sent for Refund [{id}]'.format(code=self.partner.short_code, id=refund.id)
        logger.check_present(
            (REFUND_MODEL_LOGGER_NAME, 'INFO', msg)
        )
        self.assertFalse(mock_task.called)

    @mock.patch('ecommerce_worker.sailthru.v1.tasks.send_course_refund_email.delay')
    def test_notify_purchaser_without_course_product_class(self, mock_task):
        """ Verify a notification is not sent if the refunded item is not a course seat. """
        self.site.siteconfiguration.send_refund_notifications = True

        order = create_order(site=self.site)
        product_class = order.lines.first().product.get_product_class().name
        self.assertNotEqual(product_class, SEAT_PRODUCT_CLASS_NAME)

        refund = self.create_refund(order=order)

        with LogCapture(REFUND_MODEL_LOGGER_NAME) as logger:
            refund._notify_purchaser()  # pylint: disable=protected-access

        msg = ('No refund notification will be sent for Refund [{id}]. The notification supports product '
               'lines of type Course, not [{product_class}].').format(product_class=product_class, id=refund.id)
        logger.check_present(
            (REFUND_MODEL_LOGGER_NAME, 'WARNING', msg)
        )
        self.assertFalse(mock_task.called)


class RefundLineTests(StatusTestsMixin, TestCase):
    pipeline = settings.OSCAR_REFUND_LINE_STATUS_PIPELINE

    def _get_instance(self, **kwargs):
        return RefundLineFactory(**kwargs)

    def test_deny(self):
        """ The method sets the status to Denied. """
        line = self._get_instance()
        self.assertEqual(line.status, REFUND_LINE.OPEN)
        self.assertTrue(line.deny())
        self.assertEqual(line.status, REFUND_LINE.DENIED)
