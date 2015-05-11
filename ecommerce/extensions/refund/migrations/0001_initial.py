# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion
from django.conf import settings


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
                ('total_credit_excl_tax', models.DecimalField(verbose_name='Total Credit (excl. tax)', max_digits=12, decimal_places=2)),
                ('status', models.CharField(default=b'Open', max_length=255, verbose_name='Status', choices=[(b'Open', b'Open'), (b'Denied', b'Denied'), (b'Error', b'Error'), (b'Complete', b'Complete')])),
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
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='HistoricalRefundLine',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('line_credit_excl_tax', models.DecimalField(verbose_name='Line Credit (excl. tax)', max_digits=12, decimal_places=2)),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantity')),
                ('status', models.CharField(default=b'Open', max_length=255, verbose_name='Status', choices=[(b'Open', b'Open'), (b'Denied', b'Denied'), (b'Refund Error', b'Refund Error'), (b'Refunded', b'Refunded'), (b'Revocation Error', b'Revocation Error'), (b'Complete', b'Complete')])),
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
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Refund',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('total_credit_excl_tax', models.DecimalField(verbose_name='Total Credit (excl. tax)', max_digits=12, decimal_places=2)),
                ('status', models.CharField(default=b'Open', max_length=255, verbose_name='Status', choices=[(b'Open', b'Open'), (b'Denied', b'Denied'), (b'Error', b'Error'), (b'Complete', b'Complete')])),
                ('order', models.ForeignKey(related_name='refund', verbose_name='Order', to='order.Order')),
                ('user', models.ForeignKey(related_name='refunds', verbose_name='User', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='RefundLine',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('line_credit_excl_tax', models.DecimalField(verbose_name='Line Credit (excl. tax)', max_digits=12, decimal_places=2)),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantity')),
                ('status', models.CharField(default=b'Open', max_length=255, verbose_name='Status', choices=[(b'Open', b'Open'), (b'Denied', b'Denied'), (b'Refund Error', b'Refund Error'), (b'Refunded', b'Refunded'), (b'Revocation Error', b'Revocation Error'), (b'Complete', b'Complete')])),
                ('order_line', models.ForeignKey(related_name='refund_lines', verbose_name='Order Line', to='order.Line')),
                ('refund', models.ForeignKey(related_name='lines', verbose_name='Refund', to='refund.Refund')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='historicalrefundline',
            name='refund',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='refund.Refund', null=True),
            preserve_default=True,
        ),
    ]
