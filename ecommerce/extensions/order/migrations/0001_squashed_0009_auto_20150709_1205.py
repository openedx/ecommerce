# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import oscar.models.fields.autoslugfield
import oscar.core.utils
import oscar.models.fields
import django.db.models.deletion
from django.conf import settings


# Functions from the following migrations need manual copying.
# Move them and any dependencies into this file, then update the
# RunPython operations to refer to the local versions:
# ecommerce.extensions.order.migrations.0003_auto_20150224_1520


def create_shipping_event(apps, schema_editor):
    """
    Create a single new shipping event type that can be applied to an order. This will allow us to initiate order
    shipment.
    """
    # Create all our Product Types.
    ShippingEventType = apps.get_model("order", "ShippingEventType")
    ShippingEventType.objects.create(code="shipped", name="Shipped")


class Migration(migrations.Migration):

    replaces = [(b'order', '0001_initial'), (b'order', '0002_auto_20141007_2032'), (b'order', '0003_auto_20150224_1520'), (b'order', '0004_order_payment_processor'), (b'order', '0005_deprecate_order_payment_processor'), (b'order', '0006_paymentevent_processor_name'), (b'order', '0007_create_history_tables'), (b'order', '0008_delete_order_payment_processor'), (b'order', '0009_auto_20150709_1205')]

    dependencies = [
        ('partner', '0001_squashed_0008_auto_20150914_1057'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('customer', '0001_initial'),
        ('catalogue', '0001_squashed_0010_catalog'),
        ('basket', '0002_auto_20140827_1705'),
        ('address', '0001_initial'),
        ('sites', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BillingAddress',
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
            ],
            options={
                'abstract': False,
                'verbose_name': 'Billing address',
                'verbose_name_plural': 'Billing addresses',
            },
        ),
        migrations.CreateModel(
            name='ShippingAddress',
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
                ('phone_number', oscar.models.fields.PhoneNumberField(help_text='In case we need to call you about your order', verbose_name='Phone number', blank=True)),
                ('notes', models.TextField(help_text='Tell us anything we should know when delivering your order.', verbose_name='Instructions', blank=True)),
                ('country', models.ForeignKey(verbose_name='Country', to='address.Country')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Shipping address',
                'verbose_name_plural': 'Shipping addresses',
            },
        ),
        migrations.CreateModel(
            name='Order',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('number', models.CharField(unique=True, max_length=128, verbose_name='Order number', db_index=True)),
                ('currency', models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency')),
                ('total_incl_tax', models.DecimalField(verbose_name='Order total (inc. tax)', max_digits=12, decimal_places=2)),
                ('total_excl_tax', models.DecimalField(verbose_name='Order total (excl. tax)', max_digits=12, decimal_places=2)),
                ('shipping_incl_tax', models.DecimalField(default=0, verbose_name='Shipping charge (inc. tax)', max_digits=12, decimal_places=2)),
                ('shipping_excl_tax', models.DecimalField(default=0, verbose_name='Shipping charge (excl. tax)', max_digits=12, decimal_places=2)),
                ('shipping_method', models.CharField(max_length=128, verbose_name='Shipping method', blank=True)),
                ('shipping_code', models.CharField(default='', max_length=128, blank=True)),
                ('status', models.CharField(max_length=100, verbose_name='Status', blank=True)),
                ('guest_email', models.EmailField(max_length=75, verbose_name='Guest email address', blank=True)),
                ('date_placed', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('basket', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Basket', blank=True, to='basket.Basket', null=True)),
                ('billing_address', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Billing Address', blank=True, to='order.BillingAddress', null=True)),
                ('shipping_address', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Shipping Address', blank=True, to='order.ShippingAddress', null=True)),
                ('site', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Site', to='sites.Site', null=True)),
                ('user', models.ForeignKey(related_name='orders', on_delete=django.db.models.deletion.SET_NULL, verbose_name='User', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ['-date_placed'],
                'abstract': False,
                'verbose_name': 'Order',
                'verbose_name_plural': 'Orders',
            },
        ),
        migrations.CreateModel(
            name='CommunicationEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date')),
                ('event_type', models.ForeignKey(verbose_name='Event Type', to='customer.CommunicationEventType')),
                ('order', models.ForeignKey(related_name='communication_events', verbose_name='Order', to='order.Order')),
            ],
            options={
                'ordering': ['-date_created'],
                'abstract': False,
                'verbose_name': 'Communication Event',
                'verbose_name_plural': 'Communication Events',
            },
        ),
        migrations.CreateModel(
            name='Line',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
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
                ('order', models.ForeignKey(related_name='lines', verbose_name='Order', to='order.Order')),
                ('partner', models.ForeignKey(related_name='order_lines', on_delete=django.db.models.deletion.SET_NULL, verbose_name='Partner', blank=True, to='partner.Partner', null=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Product', blank=True, to='catalogue.Product', null=True)),
                ('stockrecord', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Stock record', blank=True, to='partner.StockRecord', null=True)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Order Line',
                'verbose_name_plural': 'Order Lines',
            },
        ),
        migrations.CreateModel(
            name='LineAttribute',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=128, verbose_name='Type')),
                ('value', models.CharField(max_length=255, verbose_name='Value')),
                ('line', models.ForeignKey(related_name='attributes', verbose_name='Line', to='order.Line')),
                ('option', models.ForeignKey(related_name='line_attributes', on_delete=django.db.models.deletion.SET_NULL, verbose_name='Option', to='catalogue.Option', null=True)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Line Attribute',
                'verbose_name_plural': 'Line Attributes',
            },
        ),
        migrations.CreateModel(
            name='LinePrice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantity')),
                ('price_incl_tax', models.DecimalField(verbose_name='Price (inc. tax)', max_digits=12, decimal_places=2)),
                ('price_excl_tax', models.DecimalField(verbose_name='Price (excl. tax)', max_digits=12, decimal_places=2)),
                ('shipping_incl_tax', models.DecimalField(default=0, verbose_name='Shiping (inc. tax)', max_digits=12, decimal_places=2)),
                ('shipping_excl_tax', models.DecimalField(default=0, verbose_name='Shipping (excl. tax)', max_digits=12, decimal_places=2)),
                ('line', models.ForeignKey(related_name='prices', verbose_name='Line', to='order.Line')),
                ('order', models.ForeignKey(related_name='line_prices', verbose_name='Option', to='order.Order')),
            ],
            options={
                'ordering': ('id',),
                'abstract': False,
                'verbose_name': 'Line Price',
                'verbose_name_plural': 'Line Prices',
            },
        ),
        migrations.CreateModel(
            name='OrderDiscount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('category', models.CharField(default='Basket', max_length=64, verbose_name='Discount category', choices=[('Basket', 'Basket'), ('Shipping', 'Shipping'), ('Deferred', 'Deferred')])),
                ('offer_id', models.PositiveIntegerField(null=True, verbose_name='Offer ID', blank=True)),
                ('offer_name', models.CharField(db_index=True, max_length=128, verbose_name='Offer name', blank=True)),
                ('voucher_id', models.PositiveIntegerField(null=True, verbose_name='Voucher ID', blank=True)),
                ('voucher_code', models.CharField(db_index=True, max_length=128, verbose_name='Code', blank=True)),
                ('frequency', models.PositiveIntegerField(null=True, verbose_name='Frequency')),
                ('amount', models.DecimalField(default=0, verbose_name='Amount', max_digits=12, decimal_places=2)),
                ('message', models.TextField(blank=True)),
                ('order', models.ForeignKey(related_name='discounts', verbose_name='Order', to='order.Order')),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Order Discount',
                'verbose_name_plural': 'Order Discounts',
            },
        ),
        migrations.CreateModel(
            name='OrderNote',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('note_type', models.CharField(max_length=128, verbose_name='Note Type', blank=True)),
                ('message', models.TextField(verbose_name='Message')),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date Created')),
                ('date_updated', models.DateTimeField(auto_now=True, verbose_name='Date Updated')),
                ('order', models.ForeignKey(related_name='notes', verbose_name='Order', to='order.Order')),
                ('user', models.ForeignKey(verbose_name='User', to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'abstract': False,
                'verbose_name': 'Order Note',
                'verbose_name_plural': 'Order Notes',
            },
        ),
        migrations.CreateModel(
            name='ShippingEventType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=255, verbose_name='Name')),
                ('code', oscar.models.fields.autoslugfield.AutoSlugField(populate_from='name', editable=False, max_length=128, blank=True, unique=True, verbose_name='Code')),
            ],
            options={
                'ordering': ('name',),
                'abstract': False,
                'verbose_name': 'Shipping Event Type',
                'verbose_name_plural': 'Shipping Event Types',
            },
        ),
        migrations.CreateModel(
            name='ShippingEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('notes', models.TextField(help_text='This could be the dispatch reference, or a tracking number', verbose_name='Event notes', blank=True)),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date Created')),
                ('event_type', models.ForeignKey(verbose_name='Event Type', to='order.ShippingEventType')),
                ('order', models.ForeignKey(related_name='shipping_events', verbose_name='Order', to='order.Order')),
            ],
            options={
                'ordering': ['-date_created'],
                'abstract': False,
                'verbose_name': 'Shipping Event',
                'verbose_name_plural': 'Shipping Events',
            },
        ),
        migrations.CreateModel(
            name='ShippingEventQuantity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('quantity', models.PositiveIntegerField(verbose_name='Quantity')),
                ('event', models.ForeignKey(related_name='line_quantities', verbose_name='Event', to='order.ShippingEvent')),
                ('line', models.ForeignKey(related_name='shipping_event_quantities', verbose_name='Line', to='order.Line')),
            ],
            options={
                'verbose_name': 'Shipping Event Quantity',
                'verbose_name_plural': 'Shipping Event Quantities',
            },
        ),
        migrations.AlterUniqueTogether(
            name='shippingeventquantity',
            unique_together=set([('event', 'line')]),
        ),
        migrations.AddField(
            model_name='shippingevent',
            name='lines',
            field=models.ManyToManyField(related_name='shipping_events', verbose_name='Lines', through='order.ShippingEventQuantity', to=b'order.Line'),
        ),
        migrations.CreateModel(
            name='PaymentEventType',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=128, verbose_name='Name')),
                ('code', oscar.models.fields.autoslugfield.AutoSlugField(populate_from='name', editable=False, max_length=128, blank=True, unique=True, verbose_name='Code')),
            ],
            options={
                'ordering': ('name',),
                'abstract': False,
                'verbose_name': 'Payment Event Type',
                'verbose_name_plural': 'Payment Event Types',
            },
        ),
        migrations.CreateModel(
            name='PaymentEvent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('amount', models.DecimalField(verbose_name='Amount', max_digits=12, decimal_places=2)),
                ('reference', models.CharField(max_length=128, verbose_name='Reference', blank=True)),
                ('processor_name', models.CharField(max_length=32, null=True, verbose_name='Payment Processor', blank=True)),
                ('date_created', models.DateTimeField(auto_now_add=True, verbose_name='Date created')),
                ('event_type', models.ForeignKey(verbose_name='Event Type', to='order.PaymentEventType')),
                ('order', models.ForeignKey(related_name='payment_events', verbose_name='Order', to='order.Order')),
                ('shipping_event', models.ForeignKey(related_name='payment_events', to='order.ShippingEvent', null=True)),
            ],
            options={
                'ordering': ['-date_created'],
                'abstract': False,
                'verbose_name': 'Payment Event',
                'verbose_name_plural': 'Payment Events',
            },
        ),
        migrations.CreateModel(
            name='PaymentEventQuantity',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('quantity', models.PositiveIntegerField(verbose_name='Quantity')),
                ('event', models.ForeignKey(related_name='line_quantities', verbose_name='Event', to='order.PaymentEvent')),
                ('line', models.ForeignKey(related_name='payment_event_quantities', verbose_name='Line', to='order.Line')),
            ],
            options={
                'verbose_name': 'Payment Event Quantity',
                'verbose_name_plural': 'Payment Event Quantities',
            },
        ),
        migrations.AddField(
            model_name='paymentevent',
            name='lines',
            field=models.ManyToManyField(to=b'order.Line', verbose_name='Lines', through='order.PaymentEventQuantity'),
        ),
        migrations.AlterUniqueTogether(
            name='paymenteventquantity',
            unique_together=set([('event', 'line')]),
        ),
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
                ('date_placed', models.DateTimeField(db_index=True)),
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
        ),
    ]
