# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offer', '0006_auto_20161025_1446'),
    ]

    operations = [
        migrations.AlterField(
            model_name='range',
            name='catalog_query',
            field=models.TextField(null=True, blank=True),
        ),
    ]
