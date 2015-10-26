from __future__ import unicode_literals
from StringIO import StringIO

from django.core.management import call_command
from django.test import TestCase
from oscar.core.loading import get_model
from oscar.test import factories

Basket = get_model('basket', 'Basket')


class DeleteOrderedBasketsCommandTests(TestCase):
    command = 'delete_ordered_baskets'

    def setUp(self):
        super(DeleteOrderedBasketsCommandTests, self).setUp()

        # Create baskets with and without orders
        self.orders = [factories.create_order() for __ in range(0, 2)]
        self.unordered_baskets = [factories.BasketFactory() for __ in range(0, 3)]

    def test_without_commit(self):
        """ Verify the command does not delete baskets if the commit flag is not set. """
        expected = Basket.objects.count()

        # Call the command with dry-run flag
        out = StringIO()
        call_command(self.command, commit=False, stderr=out)

        # Verify no baskets deleted
        self.assertEqual(Basket.objects.count(), expected)

        # Verify the number of baskets expected to be deleted was printed to stderr
        expected = 'This is a dry run. Had the --commit flag been included, [{}] baskets would have been deleted.'.\
            format(len(self.orders))
        self.assertEqual(out.getvalue().strip(), expected)

    def test_with_commit(self):
        """ Verify the command, when called with the commit flag, deletes baskets with orders. """
        # Verify we have baskets with orders
        self.assertEqual(Basket.objects.filter(order__isnull=False).count(), len(self.orders))

        # Call the command with the commit flag
        out = StringIO()
        call_command(self.command, commit=True, stderr=out)

        # Verify baskets with orders deleted
        self.assertEqual(list(Basket.objects.all()), self.unordered_baskets)

        # Verify info was output to stderr
        expected = 'Deleting [{}] baskets...\nDone.'.format(len(self.orders))
        self.assertEqual(out.getvalue().strip(), expected)
