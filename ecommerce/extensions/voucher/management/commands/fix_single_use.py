""" This command fixes SINGLE_USE vouchers."""
import logging

from django.core.management import BaseCommand

from oscar.core.loading import get_model

logger = logging.getLogger(__name__)

Voucher = get_model('voucher', 'Voucher')


class Command(BaseCommand):
    """
    Fix all SINGLE_USE vouchers.
    Some SINGLE_USE vouchers may have been created with the wrong max_applications set.
    This command sets their max_global_applications to the default value.
    """

    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    def handle(self, *args, **options):
        vouchers = Voucher.objects.filter(usage=Voucher.SINGLE_USE, offers__max_global_applications=1)
        for v in vouchers:
            offer = v.offers.first()
            logger.info('Modifying Voucher %s.', v.name)
            offer.max_global_applications = None
            offer.save()
