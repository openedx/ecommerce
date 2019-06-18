# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-08-28 11:22
from __future__ import unicode_literals

from __future__ import absolute_import
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0013_partner_default_site'),
        ('offer', '0017_condition_journal_bundle_uuid'),
    ]

    operations = [
        migrations.AddField(
            model_name='conditionaloffer',
            name='partner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='partner.Partner'),
        ),
    ]
