""" Adds a Site to Referrals where site is set to null. """


from django.contrib.sites.models import Site
from django.core.management import BaseCommand, CommandError

from ecommerce.referrals.models import Referral


class Command(BaseCommand):
    help = 'Add a site to referrals without one.'

    def add_arguments(self, parser):
        parser.add_argument('-s', '--site-id',
                            action='store',
                            dest='site_id',
                            type=int,
                            help='ID of the Site to associate the referrals with.')
        parser.add_argument('--commit',
                            action='store_true',
                            dest='commit',
                            default=False,
                            help='Actually update the referrals.')

    def handle(self, *args, **options):
        queryset = Referral.objects.filter(site__isnull=True)
        count = queryset.count()

        try:
            site = Site.objects.get(id=options['site_id'])
        except Site.DoesNotExist:
            msg = 'A valid Site ID must be specified!'
            self.stderr.write(msg)
            raise CommandError(msg)

        if options['commit']:
            self.stdout.write('Associating [{}] referrals with site [{}]...'.format(count, site))

            queryset.update(site=site)
            self.stdout.write('Done.')
        else:
            msg = 'This has been an example operation. If the --commit flag had been included, the command ' \
                  'would have associated [{}] referrals with site [{}].'.format(count, site)
            self.stdout.write(msg)
