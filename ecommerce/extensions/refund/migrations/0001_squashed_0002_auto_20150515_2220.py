# -*- coding: utf-8 -*-


import django.db.models.deletion
import django.utils.timezone
import django_extensions.db.fields
import oscar.core.utils
from django.conf import settings
from django.db import migrations, models

import ecommerce.extensions.refund.models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0008_delete_order_payment_processor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalRefund',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('total_credit_excl_tax', models.DecimalField(verbose_name='Total Credit (excl. tax)', max_digits=12, decimal_places=2)),
                ('currency', models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency')),
                ('status', models.CharField(max_length=255, verbose_name='Status')),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('order', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='order.Order', null=True)),
                ('user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical refund',
            },
        ),
        migrations.CreateModel(
            name='HistoricalRefundLine',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('line_credit_excl_tax', models.DecimalField(verbose_name='Line Credit (excl. tax)', max_digits=12, decimal_places=2)),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantity')),
                ('status', models.CharField(max_length=255, verbose_name='Status')),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('order_line', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='order.Line', null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical refund line',
            },
        ),
        migrations.CreateModel(
            name='Refund',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('total_credit_excl_tax', models.DecimalField(verbose_name='Total Credit (excl. tax)', max_digits=12, decimal_places=2)),
                ('currency', models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency')),
                ('status', models.CharField(max_length=255, verbose_name='Status')),
                ('order', models.ForeignKey(related_name='refunds', verbose_name='Order', to='order.Order', on_delete=models.CASCADE)),
                ('user', models.ForeignKey(related_name='refunds', verbose_name='User', to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
            bases=(ecommerce.extensions.refund.models.StatusMixin, models.Model),
        ),
        migrations.CreateModel(
            name='RefundLine',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('line_credit_excl_tax', models.DecimalField(verbose_name='Line Credit (excl. tax)', max_digits=12, decimal_places=2)),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantity')),
                ('status', models.CharField(max_length=255, verbose_name='Status')),
                ('order_line', models.ForeignKey(related_name='refund_lines', verbose_name='Order Line', to='order.Line', on_delete=models.CASCADE)),
                ('refund', models.ForeignKey(related_name='lines', verbose_name='Refund', to='refund.Refund', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
            bases=(ecommerce.extensions.refund.models.StatusMixin, models.Model),
        ),
        migrations.AddField(
            model_name='historicalrefundline',
            name='refund',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='refund.Refund', null=True),
        ),
    ]
