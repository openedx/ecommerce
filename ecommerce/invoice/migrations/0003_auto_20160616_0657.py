# -*- coding: utf-8 -*-


import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0002_auto_20160324_1919'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalinvoice',
            name='discount_type',
            field=models.CharField(default=b'Percentage', max_length=255, null=True, blank=True, choices=[(b'Percentage', 'Percentage'), (b'Fixed', 'Fixed')]),
        ),
        migrations.AddField(
            model_name='historicalinvoice',
            name='discount_value',
            field=models.PositiveIntegerField(null=True, blank=True),
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
            field=models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.AddField(
            model_name='historicalinvoice',
            name='type',
            field=models.CharField(default=b'Prepaid', max_length=255, null=True, blank=True, choices=[(b'Prepaid', 'Prepaid'), (b'Postpaid', 'Postpaid'), (b'Not applicable', 'Not applicable')]),
        ),
        migrations.AddField(
            model_name='invoice',
            name='discount_type',
            field=models.CharField(default=b'Percentage', max_length=255, null=True, blank=True, choices=[(b'Percentage', 'Percentage'), (b'Fixed', 'Fixed')]),
        ),
        migrations.AddField(
            model_name='invoice',
            name='discount_value',
            field=models.PositiveIntegerField(null=True, blank=True),
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
            field=models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.AddField(
            model_name='invoice',
            name='type',
            field=models.CharField(default=b'Prepaid', max_length=255, null=True, blank=True, choices=[(b'Prepaid', 'Prepaid'), (b'Postpaid', 'Postpaid'), (b'Not applicable', 'Not applicable')]),
        ),
    ]
