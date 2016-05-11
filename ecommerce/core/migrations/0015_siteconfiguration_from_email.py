# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_enrollment_code_switch'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='from_email',
            field=models.CharField(default='oscar@example.com', help_text='Address from which emails are sent.', max_length=255, verbose_name='From email'),
            preserve_default=False,
        ),
    ]
