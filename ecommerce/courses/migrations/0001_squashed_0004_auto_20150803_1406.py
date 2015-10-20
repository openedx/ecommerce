# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    replaces = [(b'courses', '0001_initial'), (b'courses', '0002_historicalcourse'), (b'courses', '0003_auto_20150618_1108'), (b'courses', '0004_auto_20150803_1406')]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.CharField(max_length=255, serialize=False, verbose_name=b'ID', primary_key=True)),
                ('name', models.CharField(max_length=255)),
                ('thumbnail_url', models.URLField(null=True, blank=True)),
                ('verification_deadline', models.DateTimeField(help_text='Last date/time on which verification for this product can be submitted.', null=True, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalCourse',
            fields=[
                ('id', models.CharField(max_length=255, verbose_name=b'ID', db_index=True)),
                ('name', models.CharField(max_length=255)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('thumbnail_url', models.URLField(null=True, blank=True)),
                ('verification_deadline', models.DateTimeField(help_text='Last date/time on which verification for this product can be submitted.', null=True, blank=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical course',
            },
        ),
    ]
