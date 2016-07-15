import ddt
from django.conf import settings
import httpretty
import mock
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_model, get_class
from oscar.test.newfactories import UserFactory
from testfixtures import LogCapture

from ecommerce.core.url_utils import get_lms_enrollment_api_url
from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.extensions.refund import models
from ecommerce.extensions.refund.exceptions import InvalidStatus
from ecommerce.extensions.refund.status import REFUND, REFUND_LINE
from ecommerce.extensions.refund.tests.factories import RefundFactory, RefundLineFactory
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.testcases import TestCase

post_refund = get_class('refund.signals', 'post_refund')
Refund = get_model('refund', 'Refund')

LOGGER_NAME = 'ecommerce.extensions.analytics.utils'


class StatusTestsMixin(object):
    pipeline = None

    def _get_instance(self, **kwargs):
        """ Generate an instance of the model being tested. """
        raise NotImplementedError

    def test_available_statuses(self):
        """ Verify available_statuses() returns a list of statuses corresponding to the pipeline. """

        for status, allowed_transitions in self.pipeline.iteritems():
            instance = self._get_instance(status=status)
            self.assertEqual(instance.available_statuses(), allowed_transitions)

    def test_set_status_invalid_status(self):
        """ Verify attempts to set the status to an invalid value raise an exception. """

        for status, valid_statuses in self.pipeline.iteritems():
            instance = self._get_instance(status=status)

            all_statuses = self.pipeline.keys()
            invalid_statuses = set(all_statuses) - set(valid_statuses)

            for new_status in invalid_statuses:
                self.assertRaises(InvalidStatus, instance.set_status, new_status)
                self.assertEqual(instance.status, status,
                                 'Refund status should not be changed when attempting to set an invalid status.')

    def test_set_status_valid_status(self):
        """ Verify status is updated when attempting to transition to a valid status. """

        for status, valid_statuses in self.pipeline.iteritems():
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
        self.assertEqual(Refund.all_statuses(), self.pipeline.keys())

    @ddt.data(False, True)
    def test_create_with_lines(self, multiple_lines):
        """
        Given an order and order lines that have not been refunded, Refund.create_with_lines
        should create a Refund with corresponding RefundLines.
        """
        order = self.create_order(user=UserFactory(), multiple_lines=multiple_lines)

        with LogCapture(LOGGER_NAME) as l:
            refund = Refund.create_with_lines(order, list(order.lines.all()))

            l.check(
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

        self.assert_refund_matches_order(refund, order)

    def test_create_with_lines_with_existing_refund(self):
        """
        Refund.create_with_lines should not create RefundLines for order lines
        which have already been refunded.
        """
        order = self.create_order(user=UserFactory())
        line = order.lines.first()
        RefundLineFactory(order_line=line)

        with LogCapture(LOGGER_NAME) as l:
            refund = Refund.create_with_lines(order, [line])
            self.assertEqual(refund, None)

            l.check()

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

        refund = Refund.create_with_lines(order, list(order.lines.all()))

        # Verify that refund lines are not revoked.
        self.assertFalse(mock_revoke_line.called)

        # Verify that the refund has been successfully approved.
        self.assertEqual(refund.status, REFUND.COMPLETE)
        self.assertEqual(set([line.status for line in refund.lines.all()]), {REFUND_LINE.COMPLETE})

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

    def test_approve(self):
        """
        If payment refund and fulfillment revocation succeed, the method should update the status of the Refund and
        RefundLine objects to Complete, and return True.
        """
        self.site.siteconfiguration.segment_key = None
        refund = self.create_refund()

        with mock.patch.object(DummyProcessor, 'issue_credit', return_value=True):
            with LogCapture(LOGGER_NAME) as l:

                self.approve(refund)

                l.check(
                    (
                        LOGGER_NAME,
                        'INFO',
                        'credit_issued: amount="{}", currency="{}", processor_name="{}", '
                        'refund_id="{}", user_id="{}"'.format(
                            refund.total_credit_excl_tax,
                            refund.currency,
                            refund.order.sources.first().source_type.name,
                            refund.id,
                            refund.user.id
                        )
                    )
                )

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

    @ddt.data(REFUND.COMPLETE, REFUND.DENIED)
    def test_approve_wrong_state(self, status):
        """ The method should return False if the Refund cannot be approved. """
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

    def test_deny_with_exception(self):
        """
        If denial of a line results in an exception being raised, the exception should be logged, and the method
        should return False.
        """
        # Create a Refund
        refund = self._get_instance()

        # Make RefundLine.deny() raise an exception
        with mock.patch('ecommerce.extensions.refund.models.RefundLine.deny', side_effect=Exception):
            logger_name = 'ecommerce.extensions.refund.models'

            with LogCapture(logger_name) as l:
                self.assertFalse(refund.deny())
                l.check((logger_name, 'ERROR', 'Failed to deny RefundLine [{}].'.format(refund.lines.first().id)))

    @ddt.data(REFUND.REVOCATION_ERROR, REFUND.PAYMENT_REFUNDED, REFUND.PAYMENT_REFUND_ERROR, REFUND.COMPLETE)
    def test_deny_wrong_state(self, status):
        """ The method should return False if the Refund cannot be denied. """
        refund = self._get_instance(status=status)
        self.assertEqual(refund.status, status)
        self.assert_line_status(refund, REFUND_LINE.OPEN)

        self.assertFalse(refund.deny())
        self.assertEqual(refund.status, status)
        self.assert_line_status(refund, REFUND_LINE.OPEN)


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
