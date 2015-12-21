# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

Category = get_model("catalogue", "Category")
Product = get_model("catalogue", "Product")
ProductCategory = get_model("catalogue", "ProductCategory")


def create_default_categories(apps, schema_editor):
    """Create default coupon categories."""
    categories = (
        'Coupons > Affiliate Promotion',
        'Coupons > Bulk Enrollment',
        'Coupons > ConnectEd',
        'Coupons > Course Promotion',
        'Coupons > Customer Service',
        'Coupons > Financial Assistance',
        'Coupons > Geography Promotion',
        'Coupons > Marketing Partner Promotion',
        'Coupons > Marketing-Other',
        'Coupons > Paid Cohort',
        'Coupons > Retention Promotion',
        'Coupons > Services-Other',
        'Coupons > Support-Other',
        'Coupons > Upsell Promotion',
        'Coupons > Other'
    )
    for breadcrumbs in categories:
        create_from_breadcrumbs(breadcrumbs)


def remove_default_categories(apps, schema_editor):
    """Remove default coupon categories."""
    default_categories = [
        'Affiliate Promotion', 'Bulk Enrollment', 'ConnectEd', 'Course Promotion',
        'Customer Service', 'Financial Assistance', 'Geography Promotion',
        'Marketing Partner Promotion', 'Marketing-Other', 'Paid Cohort', 'Other',
        'Retention Promotion', 'Services-Other', 'Support-Other', 'Upsell Promotion',
    ]
    for category in default_categories:
        Category.objects.get(name=category).delete()


def assign_categories_to_coupons(self, schema_editor):
    category = create_from_breadcrumbs('Coupons > Existing_coupon')
    existing_coupons = Product.objects.filter(product_class__name="Coupon")
    for coupon in existing_coupons:
        existing_categories = ProductCategory.objects.filter(product=coupon)
        # If the coupon doesn't have categories or has more then the limit (1)
        # remove the existing and assign the default one
        if existing_categories.count() != 1:
            existing_categories.delete()
            ProductCategory.objects.create(product=coupon, category=category)


def remove_categories_from_coupons(self, schema_editor):
    category = create_from_breadcrumbs('Coupons > Existing_coupon')
    existing_coupons = Product.objects.filter(product_class__name="Coupon")
    for coupon in existing_coupons:
        ProductCategory.objects.get(product=coupon, category=category).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0014_alter_couponvouchers_attribute')
    ]
    operations = [
        migrations.RunPython(create_default_categories, remove_default_categories),
        migrations.RunPython(assign_categories_to_coupons, remove_categories_from_coupons)
    ]
