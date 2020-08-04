"""
This command change priority of conditional offers.
"""


import logging

from django.core.management import BaseCommand
from django.template.defaultfilters import pluralize
from oscar.core.loading import get_model

from ecommerce.extensions.offer.models import OFFER_PRIORITY_VOUCHER
from ecommerce.extensions.order.management.commands.prompt import query_yes_no

ConditionalOffer = get_model('offer', 'ConditionalOffer')
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Change conditional offers` priority to OFFER_PRIORITY_VOUCHER.

    Example:

        ./manage.py change_priority_of_offers
    """

    help = "Changes conditional offers' priority to {}.".format(OFFER_PRIORITY_VOUCHER)
    CONFIRMATION_PROMPT = u"You're going to change priority of {count} conditional offer{pluralized}. " \
                          u"Do you want to continue?"

    def add_arguments(self, parser):
        parser.add_argument(
            '--offset',
            dest='offset',
            default=0,
            help='index to start from.',
            type=int,
        )
        parser.add_argument(
            '--limit',
            dest='limit',
            default=1000,
            help='Number of offers to update.',
            type=int,
        )
        parser.add_argument(
            '--priority',
            dest='priority',
            default=5,
            help='Priority of the Offers witch needs to be updated',
            type=int,
        )

    def handle(self, *args, **options):
        limit = options['limit']
        offset = options['offset']
        priority = options['priority']

        try:
            conditional_offers = ConditionalOffer.objects.filter(
                offer_type=ConditionalOffer.VOUCHER,
                priority=priority
            )[offset:offset + limit]

            count = len(conditional_offers)
            if count == 0:
                logger.info('No offer found which needs a priority fix')
                return

            line_feed = '\n'
            offer_names = 'Conditional offers to be updated{line_feed}'.format(line_feed=line_feed)
            for i in range(count):
                if i == count - 1:
                    line_feed = ''
                offer_names = '{names}{index}. {name}{line_feed}'.format(
                    names=offer_names, index=i + 1, name=conditional_offers[i].name, line_feed=line_feed
                )

            # List down all conditional which needs to be updated.
            logger.warning(offer_names)

            pluralized = pluralize(count)
            if query_yes_no(self.CONFIRMATION_PROMPT.format(count=count, pluralized=pluralized), default="no"):
                for offer in conditional_offers:
                    offer.priority = OFFER_PRIORITY_VOUCHER
                    offer.save()
                logger.info('Operation completed. %d conditional offer%s updated successfully.', count, pluralized)
            else:
                logger.info('Operation canceled.')

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception('Command execution failed while executing batch %d,%d\n%s', offset, limit, exc)
