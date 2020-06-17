"""
This command removes partner conditional offers.
"""


import logging

from django.core.management import BaseCommand
from django.db.models import signals
from django.template.defaultfilters import pluralize
from oscar.apps.offer.signals import delete_unused_related_conditions_and_benefits
from oscar.core.loading import get_model

from ecommerce.extensions.order.management.commands.prompt import query_yes_no

Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
logger = logging.getLogger(__name__)
Range = get_model('offer', 'Range')


class Command(BaseCommand):
    """
    Removes partner conditional offers.

    Example:

        ./manage.py remove_partner_offers --partner edX
    """

    help = 'Remove duplicate conditional offers.'
    CONFIRMATION_PROMPT = u"You're going to remove {count} conditional offer{pluralized}. Do you want to continue?"

    def add_arguments(self, parser):
        parser.add_argument('--partner',
                            action='store',
                            dest='partner',
                            type=str,
                            required=True,
                            help='Partner code to be updated.')

    def handle(self, *args, **options):
        partner_code = options['partner']

        catalogs = Catalog.objects.filter(partner__short_code__iexact=partner_code)
        ranges = Range.objects.filter(catalog__in=catalogs).distinct()
        benefits = Benefit.objects.filter(range__in=ranges).distinct()
        conditional_offers = ConditionalOffer.objects.filter(benefit__in=benefits).distinct()

        count = len(conditional_offers)
        if count == 0:
            logger.info('No offer found for partner [%s].', partner_code)
            return

        line_feed = '\n'
        offer_names = 'Conditional offers to be deleted for partner [{partner_code}] {line_feed}'.format(
            partner_code=partner_code, line_feed=line_feed
        )
        for i in range(count):
            if i == count - 1:
                line_feed = ''
            offer_names = '{names} {index}. {name} {line_feed}'.format(
                names=offer_names, index=i + 1, name=conditional_offers[i].name, line_feed=line_feed
            )

        # List down all conditional offers to be deleted.
        logger.warning(offer_names)

        pluralized = pluralize(count)
        if query_yes_no(self.CONFIRMATION_PROMPT.format(count=count, pluralized=pluralized), default="no"):
            # disconnect post_delete oscar receiver to avoid Condition matching query does not exist.
            signals.post_delete.disconnect(
                receiver=delete_unused_related_conditions_and_benefits, sender=ConditionalOffer
            )

            # delete partner related conditional offers.
            conditional_offers.delete()

            # re-connect post_delete oscar receiver.
            signals.post_delete.connect(
                receiver=delete_unused_related_conditions_and_benefits, sender=ConditionalOffer
            )
            logger.info('%d conditional offer%s removed successfully.', count, pluralized)
        else:
            logger.info('Operation canceled.')
            return
