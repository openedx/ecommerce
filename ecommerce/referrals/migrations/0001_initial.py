# -*- coding: utf-8 -*-


import django.utils.timezone
import django_extensions.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0006_basket_site'),
        ('order', '0009_auto_20150709_1205'),
    ]

    operations = [
        migrations.CreateModel(
            name='Referral',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(default=django.utils.timezone.now, verbose_name='created', editable=False, blank=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(default=django.utils.timezone.now, verbose_name='modified', editable=False, blank=True)),
                ('affiliate_id', models.CharField(default=None, max_length=255, verbose_name='Affiliate ID')),
                ('basket', models.OneToOneField(null=True, blank=True, to='basket.Basket', on_delete=models.CASCADE)),
                ('order', models.OneToOneField(null=True, blank=True, to='order.Order', on_delete=models.CASCADE)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
    ]
