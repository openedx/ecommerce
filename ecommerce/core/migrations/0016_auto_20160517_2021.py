# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_siteconfiguration_from_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='siteconfiguration',
            name='oauth_settings',
            field=jsonfield.fields.JSONField(default={}, help_text='JSON string containing OAuth backend settings.', verbose_name='OAuth settings', blank=True),
        ),
    ]
