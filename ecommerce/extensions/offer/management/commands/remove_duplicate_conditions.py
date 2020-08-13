"""
This command removes the duplicate conditions.
"""


import logging

from django.core.management import BaseCommand
from django.db.models import Count
from django.template.defaultfilters import pluralize
from oscar.core.loading import get_model

Condition = get_model('offer', 'Condition')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Removes the duplicate conditions.

    Example:

        ./manage.py remove_duplicate_conditions.
    """

    help = "Removes the duplicate conditions."

    def get_duplicate_records(self):
        return Condition.objects.values(
            'type',
            'value',
            'proxy_class',
            'enterprise_customer_uuid',
            'enterprise_customer_name',
            'enterprise_customer_catalog_uuid'
        ).annotate(id_count=Count('id')).order_by().filter(
            id_count__gt=1,
            value__isnull=False,
            proxy_class__isnull=False,
            enterprise_customer_name__isnull=False
        )

    def handle(self, *args, **options):
        duplicate_records = self.get_duplicate_records()
        duplicate_count = duplicate_records.count()
        logging.info('%d duplicate condition%s found in database.', duplicate_count, pluralize(duplicate_count))

        for record in duplicate_records:
            num_of_duplicates = record.pop('id_count')
            conditions = Condition.objects.filter(**record)
            first_condition = conditions.first()
            logging.info('Condition with id [%d] has %d duplicates.', first_condition.id, int(num_of_duplicates) - 1)
            for condition in conditions.exclude(id=first_condition.id):
                conditional_offers_queryset = ConditionalOffer.objects.filter(condition=condition)
                if conditional_offers_queryset.exists():
                    conditional_offers_queryset.update(condition=first_condition)
                logging.info('Deleting condition record with id [%d].', condition.id)
                condition.delete()
