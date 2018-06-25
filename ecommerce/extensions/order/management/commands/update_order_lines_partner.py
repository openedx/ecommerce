from __future__ import unicode_literals

import logging
from textwrap import dedent

from django.core.management.base import BaseCommand, CommandError
from oscar.core.loading import get_model

from .prompt import query_yes_no

logger = logging.getLogger(__name__)
OrderLine = get_model('order', 'Line')
Partner = get_model('partner', 'Partner')


class Command(BaseCommand):
    """
    Command to update order lines partner.

    Example:

        ./manage.py update_order_lines_partner <SKU 1> <SKU 2> ... --partner edX
    """
    help = dedent(__doc__)
    CONFIRMATION_PROMPT = u"You're going to update {count} order lines. Do you want to continue?"

    def add_arguments(self, parser):
        parser.add_argument('skus',
                            type=str,
                            nargs='*',
                            metavar='SKU',
                            help='SKUs corresponding to the product for which order lines will be updated.')
        parser.add_argument('--partner',
                            action='store',
                            dest='partner',
                            type=str,
                            required=True,
                            help='Partner code to be updated.')

    def handle(self, *args, **options):
        skus = options['skus']
        partner_code = options['partner']

        if not len(skus):
            msg = 'update_order_lines_partner requires one or more <SKU>s.'
            logger.exception(msg)
            raise CommandError(msg)

        try:
            partner = Partner.objects.get(short_code__iexact=partner_code)
        except Partner.DoesNotExist:
            msg = 'No Partner exists for code {}.'.format(partner_code)
            logger.exception(msg)
            raise CommandError(msg)

        order_lines = OrderLine.objects.filter(partner_sku__in=skus).exclude(partner=partner)
        count = len(order_lines)
        if query_yes_no(self.CONFIRMATION_PROMPT.format(count=count), default="no"):
            order_lines.update(partner=partner, partner_name=partner.name)
            logger.info('%d order lines updated.', count)
        else:
            logger.info('Operation canceled.')
            return
