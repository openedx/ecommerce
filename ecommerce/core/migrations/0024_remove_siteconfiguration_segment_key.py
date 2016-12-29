# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_siteconfiguration_analytics_configuration'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='siteconfiguration',
            name='segment_key',
        ),
    ]
