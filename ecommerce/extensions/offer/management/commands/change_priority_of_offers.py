"""
This command change priority of conditional offers.
"""
from __future__ import unicode_literals

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

    def handle(self, *args, **options):
        conditional_offers = ConditionalOffer.objects.filter(
            offer_type=ConditionalOffer.VOUCHER
        ).exclude(priority=OFFER_PRIORITY_VOUCHER)

        count = len(conditional_offers)
        if count == 0:
            logger.info('No offer found which needs a priority fix')
            return

        line_feed = '\n'
        offer_names = 'Conditional offers to be updated {line_feed}'.format(line_feed=line_feed)
        for i in range(count):
            if i == count - 1:
                line_feed = ''
            offer_names = '{names} {index}. {name} {line_feed}'.format(
                names=offer_names, index=i + 1, name=conditional_offers[i].name, line_feed=line_feed
            )

        # List down all conditional which needs to be updated.
        logger.warning(offer_names)

        pluralized = pluralize(count)
        if query_yes_no(self.CONFIRMATION_PROMPT.format(count=count, pluralized=pluralized), default="no"):
            conditional_offers.update(priority=OFFER_PRIORITY_VOUCHER)
            logger.info('Operation completed. %d conditional offer%s updated successfully.', count, pluralized)
        else:
            logger.info('Operation canceled.')
            return
