# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.extensions.basket.constants import PURCHASER_BEHALF_ATTRIBUTE


def create_attribute(apps, schema_editor):
    BasketAttributeType = apps.get_model('basket', 'BasketAttributeType')
    BasketAttributeType.objects.create(name=PURCHASER_BEHALF_ATTRIBUTE)


def delete_attribute(apps, schema_editor):
    BasketAttributeType = apps.get_model('basket', 'BasketAttributeType')
    BasketAttributeType.objects.get(name=PURCHASER_BEHALF_ATTRIBUTE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0011_add_email_basket_attribute_type'),
    ]

    operations = [
        migrations.RunPython(create_attribute, delete_attribute),
    ]
