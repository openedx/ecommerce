from django.test import TestCase, override_settings

from ecommerce.extensions.refund.exceptions import InvalidStatus
from ecommerce.extensions.refund.status import REFUND, REFUND_LINE
from ecommerce.extensions.refund.tests.factories import RefundFactory, RefundLineFactory


OSCAR_REFUND_STATUS_PIPELINE = {
    REFUND.OPEN: (REFUND.DENIED, REFUND.ERROR, REFUND.COMPLETE),
    REFUND.ERROR: (REFUND.COMPLETE, REFUND.ERROR),
    REFUND.DENIED: (),
    REFUND.COMPLETE: ()
}

OSCAR_REFUND_LINE_STATUS_PIPELINE = {
    REFUND_LINE.OPEN: (REFUND_LINE.DENIED, REFUND_LINE.PAYMENT_REFUND_ERROR, REFUND_LINE.PAYMENT_REFUNDED),
    REFUND_LINE.PAYMENT_REFUND_ERROR: (REFUND_LINE.PAYMENT_REFUNDED,),
    REFUND_LINE.PAYMENT_REFUNDED: (REFUND_LINE.COMPLETE, REFUND_LINE.REVOCATION_ERROR),
    REFUND_LINE.REVOCATION_ERROR: (REFUND_LINE.COMPLETE,),
    REFUND_LINE.DENIED: (),
    REFUND_LINE.COMPLETE: ()
}


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


@override_settings(OSCAR_REFUND_STATUS_PIPELINE=OSCAR_REFUND_STATUS_PIPELINE)
class RefundTests(StatusTestsMixin, TestCase):
    pipeline = OSCAR_REFUND_STATUS_PIPELINE

    def _get_instance(self, **kwargs):
        return RefundFactory(**kwargs)


@override_settings(OSCAR_REFUND_LINE_STATUS_PIPELINE=OSCAR_REFUND_LINE_STATUS_PIPELINE)
class RefundLineTests(StatusTestsMixin, TestCase):
    pipeline = OSCAR_REFUND_LINE_STATUS_PIPELINE

    def _get_instance(self, **kwargs):
        return RefundLineFactory(**kwargs)
