# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.extensions.checkout.signals import BUNDLE


def create_attribute(apps, schema_editor):
    BasketAttributeType = apps.get_model('basket', 'BasketAttributeType')

    BasketAttributeType.objects.create(name=BUNDLE)


def delete_attribute(apps, schema_editor):
    BasketAttributeType = apps.get_model('basket', 'BasketAttributeType')
    try:
        BasketAttributeType.objects.get(name=BUNDLE).delete()
    except BasketAttributeType.DoesNotExist:
        pass

class Migration(migrations.Migration):
    dependencies = [
        ('programs', '0001_initial'),
        ('basket', '0007_auto_20160907_2040')
    ]

    operations = [
        migrations.RunPython(create_attribute, delete_attribute)
    ]
