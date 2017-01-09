""" Changes ConditionalOffer max_global_applications for single use vouchers from one to None. """

from __future__ import unicode_literals
from django.core.management import BaseCommand
from oscar.core.loading import get_model

ConditionalOffer = get_model('offer', 'ConditionalOffer')


class Command(BaseCommand):
    def handle(self, *args, **options):
        offers = ConditionalOffer.objects.filter(max_global_applications=1, vouchers__usage='Single use')
        if offers:
            for offer in offers:
                self.stdout.write(
                    'Setting max_global_applications field to None for ConditionalOffer [{}]...'.format(offer)
                )
                offer.max_global_applications = None
                offer.save()
            self.stdout.write('Done.')
        else:
            self.stdout.write('Nothing to do here.')
