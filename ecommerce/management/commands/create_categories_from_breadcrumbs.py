import logging
import os

from django.core.management.base import BaseCommand
from django.urls import reverse
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

Category = get_model("catalogue", "Category")
logger = logging.getLogger(__name__)

COUPON_CATEGORY_NAME = 'Coupons'

current_dir = os.path.dirname(__file__)
rel_path = 'coupon_category_list.txt'
full_path = os.path.join(current_dir, rel_path)
with open(full_path) as f:
    DEFAULT_CATEGORIES = f.read().splitlines()
f.close()


class Command(BaseCommand):
    help = 'Add default categories from text file'

    def handle(self, *args, **options):
        Category.skip_history_when_saving = True
        existing_categories = Category.objects.all()
        existing_category_names = [x.name for x in existing_categories]

        for category in DEFAULT_CATEGORIES:
            if category not in existing_category_names:
                create_from_breadcrumbs('{} > {}'.format(COUPON_CATEGORY_NAME, category))
