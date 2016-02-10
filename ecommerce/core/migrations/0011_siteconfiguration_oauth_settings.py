# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_add_async_sample'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='oauth_settings',
            field=jsonfield.fields.JSONField(default=b'{}', help_text='JSON string containing OAuth backend settings.', verbose_name='OAuth settings'),
        ),
    ]
