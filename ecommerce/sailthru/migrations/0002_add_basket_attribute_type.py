# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.sailthru.signals import SAILTHRU_CAMPAIGN


def create_attribute(apps, schema_editor):
    BasketAttributeType = apps.get_model('basket', 'BasketAttributeType')

    BasketAttributeType.objects.create(name=SAILTHRU_CAMPAIGN)


def delete_attribute(apps, schema_editor):
    BasketAttributeType = apps.get_model('basket', 'BasketAttributeType')
    BasketAttributeType.objects.get(name=SAILTHRU_CAMPAIGN).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('sailthru', '0001_initial'),
        ('basket', '0007_auto_20160907_2040'),
    ]

    operations = [
        migrations.RunPython(create_attribute, delete_attribute)
    ]
