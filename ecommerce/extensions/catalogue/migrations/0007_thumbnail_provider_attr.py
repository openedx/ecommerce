# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def create_thumbnail_url_attribute(apps, schema_editor):
    """Thumbnail url attribute for the credit provider"""

    # Get seat Object
    ProductClass = apps.get_model('catalogue', 'ProductClass')
    seat = ProductClass.objects.get(name='Seat')

    # Create our Product Attributes
    ProductAttribute = apps.get_model('catalogue', 'ProductAttribute')
    ProductAttribute.objects.create(
        product_class=seat,
        name='thumbnail_url',
        code='thumbnail_url',
        type='text',
        required=False
    )


def delete_thumbnail_url_attribute(apps, schema_editor):
    """For backward compatibility"""

    # Get seat Object
    ProductClass = apps.get_model('catalogue', 'ProductClass')
    seat = ProductClass.objects.get(name='Seat')

    # Delete our Product Attributes
    ProductAttribute = apps.get_model('catalogue', 'ProductAttribute')
    ProductAttribute.objects.filter(code='thumbnail_url').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0006_credit_provider_attr'),
    ]

    operations = [
        migrations.RunPython(create_thumbnail_url_attribute, delete_thumbnail_url_attribute),
    ]
