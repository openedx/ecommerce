# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('voucher', '0002_auto_20151009_0707'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='voucher',
            name='price',
        ),
        migrations.AddField(
            model_name='voucher',
            name='total_price',
            field=models.FloatField(default=0, null=True),
        ),
    ]
