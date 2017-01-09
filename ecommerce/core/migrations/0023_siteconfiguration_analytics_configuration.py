# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_auto_20161108_2101'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='analytics_configuration',
            field=jsonfield.fields.JSONField(default={b'GOOGLE_ANALYTICS': {b'TRACKING_IDS': []}, b'SEGMENT': {b'DEFAULT_WRITE_KEY': None, b'ADDITIONAL_WRITE_KEYS': []}}, help_text='JSON string containing settings related to analytics event tracking.', verbose_name='Analytics tracking configuration'),
        ),
    ]
