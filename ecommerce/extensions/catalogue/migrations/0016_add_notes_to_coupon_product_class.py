# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from oscar.core.loading import get_model

ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def add_note_to_coupon_product_class(apps, schema_editor):
    """Add optional note attribute to coupon product class."""
    coupon = ProductClass.objects.get(name='Coupon')
    ProductAttribute.objects.create(
        product_class=coupon,
        name='Note',
        code='note',
        type='text',
        required=False
    )


def remove_note_to_coupon_product_class(apps, schema_editor):
    """ Reverse note attribute. """
    ProductAttribute.objects.get(name='Note').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0015_default_categories')
    ]
    operations = [
        migrations.RunPython(add_note_to_coupon_product_class, remove_note_to_coupon_product_class)
    ]
