# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_siteconfiguration_enable_enrollment_codes'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='siteconfiguration',
            name='payment_processors',
        ),
        migrations.RemoveField(
            model_name='siteconfiguration',
            name='theme_scss_path',
        ),
    ]
