# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import oscar.core.utils


class Migration(migrations.Migration):

    replaces = [(b'basket', '0001_initial'), (b'basket', '0002_auto_20140827_1705'), (b'basket', '0003_basket_vouchers'), (b'basket', '0004_auto_20141007_2032'), (b'basket', '0005_auto_20150709_1205')]

    dependencies = [
        ('partner', '0001_squashed_0008_auto_20150914_1057'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalogue', '0001_squashed_0010_catalog'),
    ]

    operations = [
        migrations.CreateModel(
            name='Basket',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.CharField(default='Open', max_length=128, verbose_name='Status', choices=[('Open', 'Open - currently active'), ('Merged', 'Merged - superceded by another basket'), ('Saved', 'Saved - for items to be purchased later'), ('Frozen', 'Frozen - the basket cannot be modified'), ('Submitted', 'Submitted - has been ordered at the checkout')])),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date created')),
                ('date_merged', models.DateTimeField(null=True, verbose_name='Date merged', blank=True)),
                ('date_submitted', models.DateTimeField(null=True, verbose_name='Date submitted', blank=True)),
                ('owner', models.ForeignKey(related_name='baskets', verbose_name='Owner', to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Basket',
                'verbose_name_plural': 'Baskets',
            },
        ),
        migrations.CreateModel(
            name='Line',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('line_reference', models.SlugField(max_length=128, verbose_name='Line Reference')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantity')),
                ('price_currency', models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency')),
                ('price_excl_tax', models.DecimalField(null=True, verbose_name='Price excl. Tax', max_digits=12, decimal_places=2)),
                ('price_incl_tax', models.DecimalField(null=True, verbose_name='Price incl. Tax', max_digits=12, decimal_places=2)),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date Created')),
                ('basket', models.ForeignKey(related_name='lines', verbose_name='Basket', to='basket.Basket')),
                ('product', models.ForeignKey(related_name='basket_lines', verbose_name='Product', to='catalogue.Product')),
                ('stockrecord', models.ForeignKey(related_name='basket_lines', to='partner.StockRecord')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Basket line',
                'verbose_name_plural': 'Basket lines',
            },
        ),
        migrations.CreateModel(
            name='LineAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('value', models.CharField(max_length=255, verbose_name='Value')),
                ('line', models.ForeignKey(related_name='attributes', verbose_name='Line', to='basket.Line')),
                ('option', models.ForeignKey(verbose_name='Option', to='catalogue.Option')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Line attribute',
                'verbose_name_plural': 'Line attributes',
            },
        ),
        migrations.AlterUniqueTogether(
            name='line',
            unique_together=set([('basket', 'line_reference')]),
        ),
    ]
