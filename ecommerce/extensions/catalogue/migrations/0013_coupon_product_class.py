# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from oscar.core.loading import get_model

Category = get_model("catalogue", "Category")
ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def create_product_class(apps, schema_editor):
    """Create a Coupon product class."""

    coupon = ProductClass.objects.create(
        track_stock=False,
        requires_shipping=False,
        name='Coupon',
        slug='coupon',
    )

    ProductAttribute.objects.create(
        product_class=coupon,
        name='Coupon vouchers',
        code='coupon_vouchers',
        type='entity',
        required=False
    )
    # Create a category for coupons
    Category.objects.create(
        description='All Coupons',
        slug='coupons',
        depth=1,
        path='0002',
        image='',
        name='Coupons'
    )


def remove_product_class(apps, schema_editor):
    """ Reverse function. """
    Category.objects.filter(slug='coupon').delete()
    ProductClass.objects.filter(slug='coupon').delete()


def remove_enrollment_code(apps, schema_editor):
    """ Removes the enrollment code product and it's attributes. """
    Category.objects.filter(slug='enrollment_codes').delete()
    ProductClass.objects.filter(slug='enrollment_code').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0012_enrollment_code_product_class')
    ]
    operations = [
        migrations.RunPython(remove_enrollment_code),
        migrations.RunPython(create_product_class, remove_product_class)
    ]
