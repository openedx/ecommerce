# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-06-14 00:39
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_auto_20170606_0539'),
    ]

    operations = [
        migrations.AlterField(
            model_name='siteconfiguration',
            name='enable_otto_receipt_page',
            field=models.BooleanField(default=True, help_text='Enable the usage of Otto receipt page.', verbose_name='Enable Otto receipt page'),
        ),
    ]
