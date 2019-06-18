# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0004_auto_20141007_2032'),
    ]

    operations = [
        migrations.AlterField(
            model_name='basket',
            name='vouchers',
            field=models.ManyToManyField(to='voucher.Voucher', verbose_name='Vouchers', blank=True),
            preserve_default=True,
        ),
    ]
