# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0009_auto_20150709_1205'),
        ('voucher', '0002_couponvouchers'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderVouchers',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('order', models.ForeignKey(related_name='order_vouchers', to='order.Order')),
                ('vouchers', models.ManyToManyField(related_name='order_vouchers', to='voucher.Voucher', blank=True)),
            ],
        ),
    ]
