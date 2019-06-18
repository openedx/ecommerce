# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0004_auto_20150609_1215'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalstockrecord',
            name='changed_by',
        ),
        migrations.RemoveField(
            model_name='stockrecord',
            name='changed_by',
        ),
    ]
