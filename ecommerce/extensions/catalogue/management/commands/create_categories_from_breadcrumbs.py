import logging

from django.core.management.base import BaseCommand
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

Category = get_model("catalogue", "Category")
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Add default categories from breadcrumbs'

    def add_arguments(self, parser):
        parser.add_argument('category', nargs='+', type=str)

    def handle(self, *args, **options):
        categories = " > ".join(options['category'])
        Category.skip_history_when_saving = True
        create_from_breadcrumbs(categories)
