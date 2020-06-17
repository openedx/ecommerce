

from io import StringIO

from django.contrib.sites.models import Site
from django.core.management import CommandError, call_command
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.extensions.test.factories import create_order
from ecommerce.invoice.models import Invoice
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')


class DeleteOrderedBasketsCommandTests(TestCase):
    command = 'delete_ordered_baskets'

    def setUp(self):
        super(DeleteOrderedBasketsCommandTests, self).setUp()

        # Create baskets with and without orders
        self.orders = [create_order() for __ in range(0, 2)]
        self.unordered_baskets = [factories.BasketFactory() for __ in range(0, 3)]

        # Create invoiced baskets.
        self.invoiced_orders = [create_order() for __ in range(0, 2)]
        self.invoiced_baskets = [order.basket for order in self.invoiced_orders]
        for order in self.invoiced_orders:
            Invoice.objects.create(basket=order.basket, order=order)

    def test_without_commit(self):
        """ Verify the command does not delete baskets if the commit flag is not set. """
        expected = Basket.objects.count()

        # Call the command with dry-run flag
        out = StringIO()
        call_command(self.command, commit=False, stderr=out)

        # Verify no baskets deleted
        self.assertEqual(Basket.objects.count(), expected)

        # Verify the number of baskets expected to be deleted was printed to stderr
        expected = 'This has been an example operation. If the --commit flag had been included, the command ' \
                   'would have deleted [{}] baskets.'.format(len(self.orders))
        self.assertEqual(out.getvalue().strip(), expected)

    def test_with_commit(self):
        """ Verify the command, when called with the commit flag, deletes baskets with orders. """
        # Verify we have baskets with orders
        self.assertEqual(Basket.objects.filter(order__isnull=False).count(), len(self.orders + self.invoiced_orders))

        # Verify we have invoiced baskets
        self.assertEqual(Basket.objects.filter(invoice__isnull=False).count(), len(self.invoiced_baskets))

        # Call the command with the commit flag
        out = StringIO()
        call_command(self.command, commit=True, stderr=out)

        # Verify baskets with orders deleted, except for those which are invoiced
        self.assertEqual(list(Basket.objects.all()), self.unordered_baskets + self.invoiced_baskets)

        # Verify info was output to stderr
        actual = out.getvalue().strip()
        self.assertTrue(actual.startswith('Deleting [{}] baskets.'.format(len(self.orders))))
        self.assertTrue(actual.endswith('All baskets deleted.'))

    def test_commit_without_baskets(self):
        """ Verify the command does nothing if there are no baskets to delete. """
        # Delete all baskets
        Basket.objects.all().delete()

        # Call the command with the commit flag
        out = StringIO()
        call_command(self.command, commit=True, stderr=out)

        self.assertEqual(out.getvalue().strip(), 'No baskets to delete.')


class AddSiteToBasketsBasketsCommandTests(TestCase):
    command = 'add_site_to_baskets'

    def setUp(self):
        super(AddSiteToBasketsBasketsCommandTests, self).setUp()
        self.site = Site.objects.create(domain='acme.fake')
        site = Site.objects.create(domain='test.fake')
        self.associated_baskets = [factories.BasketFactory(site=site) for __ in range(0, 2)]
        self.unassociated_baskets = [factories.BasketFactory() for __ in range(0, 3)]

    def test_without_commit(self):
        """ Verify the command does not modify any baskets, if the commit flag is not specified. """
        queryset = Basket.objects.filter(site__isnull=True)
        expected = queryset.count()

        # Call the command with dry-run flag
        out = StringIO()
        call_command(self.command, site_id=self.site.id, commit=False, stderr=out)

        # Verify no baskets affected
        self.assertEqual(queryset.count(), expected)

        # Verify the number of baskets expected to be deleted was printed to stderr
        expected = 'This has been an example operation. If the --commit flag had been included, the command ' \
                   'would have associated [{}] baskets with site [{}].'.format(len(self.unassociated_baskets),
                                                                               self.site)
        self.assertEqual(out.getvalue().strip(), expected)

    def test_with_commit(self):
        """ Verify the command adds a site to baskets without one. """
        queryset = Basket.objects.filter(site=self.site)

        # There should be no baskets associated with the site
        self.assertEqual(queryset.count(), 0)

        # Call the command
        out = StringIO()
        call_command(self.command, site_id=self.site.id, commit=True, stderr=out)

        # The baskets should be associated with the site
        self.assertEqual(queryset.count(), 3)

        # There should be no unassociated baskets
        self.assertEqual(Basket.objects.filter(site__isnull=True).count(), 0)

        # Verify info was output to stderr
        actual = out.getvalue().strip()
        self.assertTrue(actual.startswith('Associating [{}] baskets with site [{}]..'.format(
            len(self.unassociated_baskets),
            self.site)))
        self.assertTrue(actual.endswith('Done.'))

    def test_without_site_id(self):
        """ Verify an error is raised if no site ID is specified. """
        with self.assertRaisesMessage(CommandError, 'A valid Site ID must be specified!'):
            call_command(self.command, commit=False)
