# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-11-06 08:53
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0027_catalogue_entitlement_option'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalproduct',
            name='history_change_reason',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='historicalproductattributevalue',
            name='history_change_reason',
            field=models.CharField(max_length=100, null=True),
        ),
    ]
