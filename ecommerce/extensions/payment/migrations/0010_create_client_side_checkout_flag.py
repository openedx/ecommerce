# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.extensions.payment.constants import CLIENT_SIDE_CHECKOUT_FLAG_NAME


def create_flag(apps, schema_editor):
    Flag = apps.get_model('waffle', 'Flag')
    note = 'This flag determines if the integrated/client-side checkout flow should be enabled.'
    Flag.objects.get_or_create(name=CLIENT_SIDE_CHECKOUT_FLAG_NAME, defaults={'note': note})


def delete_flag(apps, schema_editor):
    Flag = apps.get_model('waffle', 'Flag')
    Flag.objects.filter(name=CLIENT_SIDE_CHECKOUT_FLAG_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('payment', '0009_auto_20161025_1446'),
        ('waffle', '0001_initial'),

    ]

    operations = [
        migrations.RunPython(create_flag, reverse_code=delete_flag),

    ]
