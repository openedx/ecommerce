# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voucher', '0001_initial'),
        ('order', '0009_auto_20150709_1205'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnrollmentCode',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_created', models.DateField(auto_now_add=True)),
                ('order_line', models.ForeignKey(related_name='enrollment_codes', to='order.Line')),
                ('vouchers', models.ManyToManyField(related_name='enrollment_codes', to='voucher.Voucher', blank=True)),
            ],
        ),
    ]
