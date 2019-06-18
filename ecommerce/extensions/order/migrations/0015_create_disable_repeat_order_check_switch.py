# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-22 17:33
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations

from ecommerce.extensions.order.constants import DISABLE_REPEAT_ORDER_CHECK_SWITCH_NAME


def create_switch(apps, schema_editor):
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name=DISABLE_REPEAT_ORDER_CHECK_SWITCH_NAME, defaults={'active': False})


def delete_switch(apps, schema_editor):
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=DISABLE_REPEAT_ORDER_CHECK_SWITCH_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('order', '0014_auto_20170606_0535'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]
