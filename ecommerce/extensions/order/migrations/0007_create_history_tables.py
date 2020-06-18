# -*- coding: utf-8 -*-


import django.db.models.deletion
import oscar.core.utils
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0003_auto_20150223_1130'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('basket', '0004_auto_20141007_2032'),
        ('sites', '0001_initial'),
        ('catalogue', '0002_auto_20150223_1052'),
        ('order', '0006_paymentevent_processor_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalLine',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('partner_name', models.CharField(max_length=128, verbose_name='Partner name', blank=True)),
                ('partner_sku', models.CharField(max_length=128, verbose_name='Partner SKU')),
                ('partner_line_reference', models.CharField(help_text='This is the item number that the partner uses within their system', max_length=128, verbose_name='Partner reference', blank=True)),
                ('partner_line_notes', models.TextField(verbose_name='Partner Notes', blank=True)),
                ('title', models.CharField(max_length=255, verbose_name='Title')),
                ('upc', models.CharField(max_length=128, null=True, verbose_name='UPC', blank=True)),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantity')),
                ('line_price_incl_tax', models.DecimalField(verbose_name='Price (inc. tax)', max_digits=12, decimal_places=2)),
                ('line_price_excl_tax', models.DecimalField(verbose_name='Price (excl. tax)', max_digits=12, decimal_places=2)),
                ('line_price_before_discounts_incl_tax', models.DecimalField(verbose_name='Price before discounts (inc. tax)', max_digits=12, decimal_places=2)),
                ('line_price_before_discounts_excl_tax', models.DecimalField(verbose_name='Price before discounts (excl. tax)', max_digits=12, decimal_places=2)),
                ('unit_cost_price', models.DecimalField(null=True, verbose_name='Unit Cost Price', max_digits=12, decimal_places=2, blank=True)),
                ('unit_price_incl_tax', models.DecimalField(null=True, verbose_name='Unit Price (inc. tax)', max_digits=12, decimal_places=2, blank=True)),
                ('unit_price_excl_tax', models.DecimalField(null=True, verbose_name='Unit Price (excl. tax)', max_digits=12, decimal_places=2, blank=True)),
                ('unit_retail_price', models.DecimalField(null=True, verbose_name='Unit Retail Price', max_digits=12, decimal_places=2, blank=True)),
                ('status', models.CharField(max_length=255, verbose_name='Status', blank=True)),
                ('est_dispatch_date', models.DateField(null=True, verbose_name='Estimated Dispatch Date', blank=True)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('order', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='order.Order', null=True)),
                ('partner', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='partner.Partner', null=True)),
                ('product', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='catalogue.Product', null=True)),
                ('stockrecord', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='partner.StockRecord', null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Order Line',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='HistoricalOrder',
            fields=[
                ('id', models.IntegerField(verbose_name='ID', db_index=True, auto_created=True, blank=True)),
                ('number', models.CharField(max_length=128, verbose_name='Order number', db_index=True)),
                ('currency', models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency')),
                ('total_incl_tax', models.DecimalField(verbose_name='Order total (inc. tax)', max_digits=12, decimal_places=2)),
                ('total_excl_tax', models.DecimalField(verbose_name='Order total (excl. tax)', max_digits=12, decimal_places=2)),
                ('shipping_incl_tax', models.DecimalField(default=0, verbose_name='Shipping charge (inc. tax)', max_digits=12, decimal_places=2)),
                ('shipping_excl_tax', models.DecimalField(default=0, verbose_name='Shipping charge (excl. tax)', max_digits=12, decimal_places=2)),
                ('shipping_method', models.CharField(max_length=128, verbose_name='Shipping method', blank=True)),
                ('shipping_code', models.CharField(default=b'', max_length=128, blank=True)),
                ('status', models.CharField(max_length=100, verbose_name='Status', blank=True)),
                ('guest_email', models.EmailField(max_length=75, verbose_name='Guest email address', blank=True)),
                ('date_placed', models.DateTimeField(db_index=True, editable=False, blank=True)),
                ('payment_processor', models.CharField(max_length=32, null=True, verbose_name='Payment Processor', blank=True)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('basket', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='basket.Basket', null=True)),
                ('billing_address', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='order.BillingAddress', null=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('shipping_address', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='order.ShippingAddress', null=True)),
                ('site', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='sites.Site', null=True)),
                ('user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Order',
            },
            bases=(models.Model,),
        ),
    ]
