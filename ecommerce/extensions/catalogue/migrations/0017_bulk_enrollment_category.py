# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

Category = get_model("catalogue", "Category")

COUPON_CATEGORY_NAME = 'Coupons'
BULK_CATEGORY_NAME = 'Bulk enrollment'


def create_bulk_enrollment_category(apps, schema_editor):
    """Create default coupon categories."""
    create_from_breadcrumbs('{} > {}'.format(COUPON_CATEGORY_NAME, BULK_CATEGORY_NAME))


def remove_bulk_enrollment_category(apps, schema_editor):
    """Remove default coupon categories."""
    Category.objects.get(name=BULK_CATEGORY_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0016_coupon_note_attribute')
    ]
    operations = [
        migrations.RunPython(create_bulk_enrollment_category, remove_bulk_enrollment_category)
    ]
