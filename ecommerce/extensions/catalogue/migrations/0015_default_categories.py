# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

Category = get_model("catalogue", "Category")


def create_default_categories(apps, schema_editor):
    """Create default coupon categories."""
    categories = (
        'Coupons > NewCoursePromo',
        'Coupons > BulkEnrollment',
        'Coupons > CustomerService',
        'Coupons > Marketing-Other',
        'Coupons > PaidCohort',
        'Coupons > ConnectEd',
        'Coupons > Services-Other',
        'Coupons > FinancialAssistance',
        'Coupons > Support-Other',
    )
    for breadcrumbs in categories:
        create_from_breadcrumbs(breadcrumbs)


def remove_default_categories(apps, schema_editor):
    """Remove default coupon categories."""
    default_categories = [
        'NewCoursePromo', 'BulkEnrollment', 'CustomerService', 'Marketing-Other',
        'PaidCohort', 'ConnectEd', 'Services-Other', 'FinancialAssistance', 'Support-Other'
    ]
    for category in default_categories:
        Category.objects.get(name=category).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0014_alter_couponvouchers_attribute')
    ]
    operations = [
        migrations.RunPython(create_default_categories, remove_default_categories)
    ]
