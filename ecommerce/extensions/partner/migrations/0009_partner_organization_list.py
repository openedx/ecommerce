# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0008_auto_20150914_1057'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='organization_list',
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
    ]
