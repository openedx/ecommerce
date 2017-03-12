# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME


def create_credit_provider_attribute(apps, schema_editor):

    # Get seat Object
    ProductClass = apps.get_model('catalogue', 'ProductClass')
    seat = ProductClass.objects.get(name=SEAT_PRODUCT_CLASS_NAME)

    # Create our Product Attributes
    ProductAttribute = apps.get_model('catalogue', 'ProductAttribute')
    ProductAttribute.objects.create(
        product_class=seat,
        name='credit_provider',
        code='credit_provider',
        type='text',
        required=False
    )


def delete_credit_provider_attribute(apps, schema_editor):
    """For backward compatibility"""
    # Delete our Product Attributes
    ProductAttribute = apps.get_model('catalogue', 'ProductAttribute')
    ProductAttribute.objects.filter(code='credit_provider').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0005_auto_20150610_1355'),
    ]

    operations = [
        migrations.RunPython(create_credit_provider_attribute, delete_credit_provider_attribute),
    ]
