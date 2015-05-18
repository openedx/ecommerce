# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import oscar.core.utils
import django.utils.timezone
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('refund', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='refund',
            options={'ordering': ('-modified', '-created'), 'get_latest_by': 'modified'},
        ),
        migrations.AlterModelOptions(
            name='refundline',
            options={'ordering': ('-modified', '-created'), 'get_latest_by': 'modified'},
        ),
        migrations.AddField(
            model_name='historicalrefund',
            name='created',
            field=django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='historicalrefund',
            name='currency',
            field=models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='historicalrefund',
            name='modified',
            field=django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='historicalrefundline',
            name='created',
            field=django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='historicalrefundline',
            name='modified',
            field=django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='refund',
            name='created',
            field=django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='refund',
            name='currency',
            field=models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='refund',
            name='modified',
            field=django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='refundline',
            name='created',
            field=django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='refundline',
            name='modified',
            field=django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='refund',
            name='order',
            field=models.ForeignKey(related_name='refunds', verbose_name='Order', to='order.Order'),
            preserve_default=True,
        ),
    ]
