# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import oscar.models.fields.autoslugfield
import oscar.models.fields
import django.db.models.deletion
from django.conf import settings
import oscar.core.utils


# Functions from the following migrations need manual copying.
# Move them and any dependencies into this file, then update the
# RunPython operations to refer to the local versions:
# ecommerce.extensions.partner.migrations.0007_auto_20150914_0841

class Migration(migrations.Migration):

    replaces = [(b'partner', '0001_initial'), (b'partner', '0002_auto_20141007_2032'), (b'partner', '0003_auto_20150223_1130'), (b'partner', '0004_auto_20150609_1215'), (b'partner', '0005_auto_20150610_1355'), (b'partner', '0006_auto_20150709_1205'), (b'partner', '0007_auto_20150914_0841'), (b'partner', '0008_auto_20150914_1057')]

    dependencies = [
        ('address', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalogue', '0001_squashed_0010_catalog'),
    ]

    operations = [
        migrations.CreateModel(
            name='Partner',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', oscar.models.fields.autoslugfield.AutoSlugField(populate_from='name', editable=False, max_length=128, blank=True, unique=True, verbose_name='Code')),
                ('name', models.CharField(max_length=128, verbose_name='Name', blank=True)),
                ('users', models.ManyToManyField(related_name='partners', verbose_name='Users', to=settings.AUTH_USER_MODEL, blank=True)),
                ('short_code', models.CharField(unique=True, max_length=8)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Partner',
                'verbose_name_plural': 'Partners',
                'permissions': (('dashboard_access', 'Can access dashboard'),),
            },
        ),
        migrations.CreateModel(
            name='PartnerAddress',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(blank=True, max_length=64, verbose_name='Title', choices=[('Mr', 'Mr'), ('Miss', 'Miss'), ('Mrs', 'Mrs'), ('Ms', 'Ms'), ('Dr', 'Dr')])),
                ('first_name', models.CharField(max_length=255, verbose_name='First name', blank=True)),
                ('last_name', models.CharField(max_length=255, verbose_name='Last name', blank=True)),
                ('line1', models.CharField(max_length=255, verbose_name='First line of address')),
                ('line2', models.CharField(max_length=255, verbose_name='Second line of address', blank=True)),
                ('line3', models.CharField(max_length=255, verbose_name='Third line of address', blank=True)),
                ('line4', models.CharField(max_length=255, verbose_name='City', blank=True)),
                ('state', models.CharField(max_length=255, verbose_name='State/County', blank=True)),
                ('postcode', oscar.models.fields.UppercaseCharField(max_length=64, verbose_name='Post/Zip-code', blank=True)),
                ('search_text', models.TextField(verbose_name='Search text - used only for searching addresses', editable=False)),
                ('country', models.ForeignKey(verbose_name='Country', to='address.Country')),
                ('partner', models.ForeignKey(related_name='addresses', verbose_name='Partner', to='partner.Partner')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Partner address',
                'verbose_name_plural': 'Partner addresses',
            },
        ),
        migrations.CreateModel(
            name='StockRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('partner_sku', models.CharField(max_length=128, verbose_name='Partner SKU')),
                ('price_currency', models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency')),
                ('price_excl_tax', models.DecimalField(null=True, verbose_name='Price (excl. tax)', max_digits=12, decimal_places=2, blank=True)),
                ('price_retail', models.DecimalField(null=True, verbose_name='Price (retail)', max_digits=12, decimal_places=2, blank=True)),
                ('cost_price', models.DecimalField(null=True, verbose_name='Cost Price', max_digits=12, decimal_places=2, blank=True)),
                ('num_in_stock', models.PositiveIntegerField(null=True, verbose_name='Number in stock', blank=True)),
                ('num_allocated', models.IntegerField(null=True, verbose_name='Number allocated', blank=True)),
                ('low_stock_threshold', models.PositiveIntegerField(null=True, verbose_name='Low Stock Threshold', blank=True)),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date created')),
                ('date_updated', models.DateTimeField(auto_now=True, verbose_name='Date updated', db_index=True)),
                ('partner', models.ForeignKey(related_name='stockrecords', verbose_name='Partner', to='partner.Partner')),
                ('product', models.ForeignKey(related_name='stockrecords', verbose_name='Product', to='catalogue.Product')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Stock record',
                'verbose_name_plural': 'Stock records',
            },
        ),
        migrations.AlterUniqueTogether(
            name='stockrecord',
            unique_together=set([('partner', 'partner_sku')]),
        ),
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
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
                ('partner', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='partner.Partner', null=True)),
                ('product', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='catalogue.Product', null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical Stock record',
            },
        ),
        migrations.CreateModel(
            name='StockAlert',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('threshold', models.PositiveIntegerField(verbose_name='Threshold')),
                ('status', models.CharField(default='Open', max_length=128, verbose_name='Status', choices=[('Open', 'Open'), ('Closed', 'Closed')])),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date Created')),
                ('date_closed', models.DateTimeField(null=True, verbose_name='Date Closed', blank=True)),
                ('stockrecord', models.ForeignKey(related_name='alerts', verbose_name='Stock Record', to='partner.StockRecord'))
            ],
            options={
                'ordering': ('-date_created',),
                'abstract': False,
                'verbose_name': 'Stock alert',
                'verbose_name_plural': 'Stock alerts',
            },
        ),
    ]
