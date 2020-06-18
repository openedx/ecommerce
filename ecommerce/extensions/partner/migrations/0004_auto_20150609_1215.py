# -*- coding: utf-8 -*-


import django.db.models.deletion
import oscar.core.utils
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalogue', '0004_auto_20150609_0129'),
        ('partner', '0003_auto_20150223_1130'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalStockRecord',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('partner_sku', models.CharField(max_length=128, verbose_name='Partner SKU')),
                ('price_currency', models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency')),
                ('price_excl_tax', models.DecimalField(null=True, verbose_name='Price (excl. tax)', max_digits=12, decimal_places=2, blank=True)),
                ('price_retail', models.DecimalField(null=True, verbose_name='Price (retail)', max_digits=12, decimal_places=2, blank=True)),
                ('cost_price', models.DecimalField(null=True, verbose_name='Cost Price', max_digits=12, decimal_places=2, blank=True)),
                ('num_in_stock', models.PositiveIntegerField(null=True, verbose_name='Number in stock', blank=True)),
                ('num_allocated', models.IntegerField(null=True, verbose_name='Number allocated', blank=True)),
                ('low_stock_threshold', models.PositiveIntegerField(null=True, verbose_name='Low Stock Threshold', blank=True)),
                ('date_created', models.DateTimeField(verbose_name='Date created', editable=False, blank=True)),
                ('date_updated', models.DateTimeField(verbose_name='Date updated', db_index=True, editable=False, blank=True)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('changed_by', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to=settings.AUTH_USER_MODEL, null=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('partner', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='partner.Partner', null=True)),
                ('product', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='catalogue.Product', null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Stock record',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='stockrecord',
            name='changed_by',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
    ]
