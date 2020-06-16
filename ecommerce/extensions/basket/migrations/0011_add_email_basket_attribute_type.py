# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE


def create_attribute(apps, schema_editor):
    BasketAttributeType = apps.get_model('basket', 'BasketAttributeType')
    BasketAttributeType.objects.create(name=EMAIL_OPT_IN_ATTRIBUTE)


def delete_attribute(apps, schema_editor):
    BasketAttributeType = apps.get_model('basket', 'BasketAttributeType')
    BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0010_create_repeat_purchase_switch'),
    ]

    operations = [
        migrations.RunPython(create_attribute, delete_attribute),
    ]
