# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('offer', '0003_auto_20160517_1247'),
    ]

    operations = [
        migrations.AlterField(
            model_name='range',
            name='course_seat_types',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]
