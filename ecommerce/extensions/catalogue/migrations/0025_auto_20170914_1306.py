# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-09-14 13:06
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0024_fix_enrollment_code_slug'),
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
