import datetime

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import QuerySet
from django.utils.timezone import now
from oscar.core.loading import get_model
from oscar.test.factories import OrderFactory
from testfixtures import LogCapture

from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.core.management.commands.clean_history'
Order = get_model('order', 'Order')


def counter(fn):
    """
    Adds a call counter to the given function.
    Source: http://code.activestate.com/recipes/577534-counting-decorator/
    """
    def _counted(*largs, **kargs):
        _counted.invocations += 1
        fn(*largs, **kargs)

    _counted.invocations = 0
    return _counted


class CleanHistoryTests(TestCase):

    def test_invalid_cutoff_date(self):
        with LogCapture(LOGGER_NAME) as log:
            with self.assertRaises(CommandError):
                call_command('clean_history', '--cutoff_date=YYYY-MM-DD')
                log.check(
                    (
                        LOGGER_NAME,
                        'EXCEPTION',
                        'Failed to parse cutoff date: YYYY-MM-DD'
                    )
                )

    def test_clean_history(self):
        initial_count = 5
        OrderFactory.create_batch(initial_count)
        cutoff_date = now() + datetime.timedelta(days=1)
        self.assertEqual(Order.history.filter(history_date__lte=cutoff_date).count(), initial_count)

        QuerySet.delete = counter(QuerySet.delete)
        call_command(
            'clean_history', '--cutoff_date={}'.format(cutoff_date.strftime('%Y-%m-%d')), batch_size=1, sleep_time=1
        )
        self.assertEqual(QuerySet.delete.invocations, initial_count)
        self.assertEqual(Order.history.filter(history_date__lte=cutoff_date).count(), 0)
