""" Adds a Site to Baskets that do not already have one. """
from django.contrib.sites.models import Site
from django.core.management import BaseCommand, CommandError
from oscar.core.loading import get_model

Basket = get_model('basket', 'Basket')


class Command(BaseCommand):
    help = 'Add a site to baskets without one.'

    def add_arguments(self, parser):
        parser.add_argument('-s', '--site-id',
                            action='store',
                            dest='site_id',
                            type=int,
                            help='ID of the Site to associate the baskets with.')
        parser.add_argument('--commit',
                            action='store_true',
                            dest='commit',
                            default=False,
                            help='Actually update the baskets.')

    def handle(self, *args, **options):
        queryset = Basket.objects.filter(site__isnull=True)
        count = queryset.count()

        try:
            site = Site.objects.get(id=options['site_id'])
        except Site.DoesNotExist:
            raise CommandError('A valid Site ID must be specified!')

        if options['commit']:
            self.stderr.write('Associating [{}] baskets with site [{}]...'.format(count, site))

            queryset.update(site=site)
            self.stderr.write('Done.')
        else:
            msg = 'This has been an example operation. If the --commit flag had been included, the command ' \
                  'would have associated [{}] baskets with site [{}].'.format(count, site)
            self.stderr.write(msg)
