

from io import StringIO

from django.core.management import CommandError, call_command

from ecommerce.referrals.models import Referral
from ecommerce.referrals.tests.factories import ReferralFactory
from ecommerce.tests.testcases import TestCase


class AddSiteToReferralsCommandTests(TestCase):
    command = 'add_site_to_referrals'

    def setUp(self):
        super(AddSiteToReferralsCommandTests, self).setUp()
        self.unassociated_referrals = ReferralFactory.create_batch(3, site=None)

    def test_without_commit(self):
        """ Verify the command does not modify any referrals, if the commit flag is not specified. """
        queryset = Referral.objects.filter(site__isnull=True)
        expected = queryset.count()

        # Call the command with dry-run flag
        out = StringIO()
        call_command(self.command, site_id=self.site.id, commit=False, stdout=out)

        # Verify no referrals affected
        self.assertEqual(queryset.count(), expected)

        # Verify the number of referrals expected to be deleted was printed to stdout
        expected = ''.join(
            [
                'This has been an example operation. If the --commit flag had been included, the command ',
                'would have associated [{}] referrals with site [{}].'.format(
                    len(self.unassociated_referrals), self.site
                )
            ]
        )
        self.assertEqual(out.getvalue().strip(), expected)

    def test_with_commit(self):
        """ Verify the command adds a site to referrals without one. """
        queryset = Referral.objects.filter(site=self.site)

        # There should be no referrals associated with the site
        self.assertEqual(queryset.count(), 0)

        # Call the command
        out = StringIO()
        call_command(self.command, site_id=self.site.id, commit=True, stdout=out)

        # The referrals should be associated with the site
        self.assertEqual(queryset.count(), 3)

        # There should be no unassociated referrals
        self.assertEqual(Referral.objects.filter(site__isnull=True).count(), 0)

        # Verify info was output to stdout
        actual = out.getvalue().strip()
        self.assertTrue(
            actual.startswith(
                'Associating [{count}] referrals with site [{site}]..'.format(
                    count=len(self.unassociated_referrals),
                    site=self.site
                )
            )
        )
        self.assertTrue(actual.endswith('Done.'))

    def test_without_site_id(self):
        """ Verify an error is raised if no site ID is specified. """
        with self.assertRaisesMessage(CommandError, 'A valid Site ID must be specified!'):
            call_command(self.command, commit=False)
