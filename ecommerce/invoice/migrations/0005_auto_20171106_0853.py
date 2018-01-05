# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-11-06 08:53
from __future__ import unicode_literals

import django_extensions.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0004_auto_20170215_2234'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalinvoice',
            name='history_change_reason',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='historicalinvoice',
            name='created',
            field=django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created'),
        ),
        migrations.AlterField(
            model_name='historicalinvoice',
            name='modified',
            field=django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified'),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='created',
            field=django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created'),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='modified',
            field=django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified'),
        ),
    ]
