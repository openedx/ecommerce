# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import jsonfield.fields
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0012_auto_20161109_1456'),
    ]

    operations = [
        migrations.CreateModel(
            name='SDNCheckFailure',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('full_name', models.CharField(max_length=255)),
                ('username', models.CharField(max_length=255)),
                ('country', models.CharField(max_length=2)),
                ('sdn_check_response', jsonfield.fields.JSONField()),
            ],
            options={
                'verbose_name': 'SDN Check Failure',
            },
        ),
    ]
