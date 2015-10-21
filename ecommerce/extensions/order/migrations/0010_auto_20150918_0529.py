# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0008_auto_20150914_1057'),
        ('order', '0009_auto_20150709_1205'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalorder',
            name='partner',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, blank=True, to='partner.Partner', null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='partner',
            field=models.ForeignKey(related_name='orders', default=1, to='partner.Partner'),
            preserve_default=False,
        ),
    ]
