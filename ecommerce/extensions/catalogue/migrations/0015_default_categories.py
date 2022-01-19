# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.extensions.catalogue.utils import create_subcategories


COUPON_CATEGORY_NAME = 'Coupons'

DEFAULT_CATEGORIES = [
    'Affiliate Promotion', 'Bulk Enrollment', 'ConnectEd', 'Course Promotion',
    'Customer Service', 'Financial Assistance', 'Geography Promotion',
    'Marketing Partner Promotion', 'Marketing-Other', 'Paid Cohort', 'Other',
    'Retention Promotion', 'Services-Other', 'Support-Other', 'Upsell Promotion',
]


def create_default_categories(apps, schema_editor):
    """Create default coupon categories."""
    Category = apps.get_model("catalogue", "Category")

    Category.skip_history_when_saving = True
    create_subcategories(Category, COUPON_CATEGORY_NAME, DEFAULT_CATEGORIES)


def remove_default_categories(apps, schema_editor):
    """Remove default coupon categories."""
    Category = apps.get_model("catalogue", "Category")

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
