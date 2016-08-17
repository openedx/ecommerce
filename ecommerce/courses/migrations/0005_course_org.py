# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0004_auto_20150803_1406'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='organization',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='organization',
            field=models.CharField(max_length=100, null=True),
        ),
    ]
