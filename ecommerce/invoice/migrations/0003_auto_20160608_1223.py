# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0002_auto_20160324_1919'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalinvoice',
            name='invoice_amount',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='historicalinvoice',
            name='invoice_discount_type',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='historicalinvoice',
            name='invoice_discount_value',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='historicalinvoice',
            name='invoice_type',
            field=models.CharField(default=b'Prepaid', max_length=255, null=True, blank=True, choices=[(b'Prepaid', 'Prepaid'), (b'Postpaid', 'Postpaid')]),
        ),
        migrations.AddField(
            model_name='historicalinvoice',
            name='number',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='historicalinvoice',
            name='payment_date',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='historicalinvoice',
            name='tax_deducted_source',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='invoice',
            name='invoice_amount',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='invoice_discount_type',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='invoice_discount_value',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='invoice_type',
            field=models.CharField(default=b'Prepaid', max_length=255, null=True, blank=True, choices=[(b'Prepaid', 'Prepaid'), (b'Postpaid', 'Postpaid')]),
        ),
        migrations.AddField(
            model_name='invoice',
            name='number',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='payment_date',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='tax_deducted_source',
            field=models.BooleanField(default=False),
        ),
    ]
