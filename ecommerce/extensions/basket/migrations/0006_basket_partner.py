# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0008_auto_20150914_1057'),
        ('basket', '0005_auto_20150709_1205'),
    ]

    operations = [
        migrations.AddField(
            model_name='basket',
            name='partner',
            field=models.ForeignKey(related_name='baskets', blank=True, to='partner.Partner', null=True),
        ),
    ]
