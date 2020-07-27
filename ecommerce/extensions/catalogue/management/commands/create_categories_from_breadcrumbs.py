import logging

from django.core.management.base import BaseCommand
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

Category = get_model("catalogue", "Category")
logger = logging.getLogger(__name__)

COUPON_CATEGORY_NAME = 'Coupons'

DEFAULT_CATEGORIES = [
    'Partner No Rev - Prepay',
    'Partner No Rev - Upon Redemption',
    'Bulk Enrollment - Prepay',
    'Bulk Enrollment - Upon Redemption',
    'Bulk Enrollment - Integration',
    'edX Employee Request',
    'Partner No Rev - RAP',
    'Partner No Rev - ORAP',
    'Affiliate Promotion', 'Bulk Enrollment', 'ConnectEd', 'Course Promotion',
    'Customer Service', 'Financial Assistance', 'Geography Promotion',
    'Marketing Partner Promotion', 'Marketing-Other', 'Paid Cohort', 'Other',
    'Retention Promotion', 'Services-Other', 'Support-Other', 'Upsell Promotion',
    'On-Campus Learners',
    'Security Disclosure Reward',
    'B2B Affiliate Promotion',
]


class Command(BaseCommand):
    help = 'Add default categories from breadcrumbs'

    def handle(self, *args, **options):
        Category.skip_history_when_saving = True
        for category in DEFAULT_CATEGORIES:
            create_from_breadcrumbs('{} > {}'.format(COUPON_CATEGORY_NAME, category))
