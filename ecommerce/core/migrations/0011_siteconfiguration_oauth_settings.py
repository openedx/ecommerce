# -*- coding: utf-8 -*-


import jsonfield.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_add_async_sample'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='oauth_settings',
            field=jsonfield.fields.JSONField(default={}, help_text='JSON string containing OAuth backend settings.', verbose_name='OAuth settings'),
        ),
    ]
