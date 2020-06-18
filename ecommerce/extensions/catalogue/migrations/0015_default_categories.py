# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

Category = get_model("catalogue", "Category")

COUPON_CATEGORY_NAME = 'Coupons'

DEFAULT_CATEGORIES = [
    'Affiliate Promotion', 'Bulk Enrollment', 'ConnectEd', 'Course Promotion',
    'Customer Service', 'Financial Assistance', 'Geography Promotion',
    'Marketing Partner Promotion', 'Marketing-Other', 'Paid Cohort', 'Other',
    'Retention Promotion', 'Services-Other', 'Support-Other', 'Upsell Promotion',
]


def create_default_categories(apps, schema_editor):
    """Create default coupon categories."""
    Category.skip_history_when_saving = True

    for category in DEFAULT_CATEGORIES:
        create_from_breadcrumbs('{} > {}'.format(COUPON_CATEGORY_NAME, category))


def remove_default_categories(apps, schema_editor):
    """Remove default coupon categories."""
    Category.skip_history_when_saving = True
    Category.objects.get(name=COUPON_CATEGORY_NAME).get_children().filter(
        name__in=DEFAULT_CATEGORIES
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0014_alter_couponvouchers_attribute')
    ]
    operations = [
        migrations.RunPython(create_default_categories, remove_default_categories)
    ]
