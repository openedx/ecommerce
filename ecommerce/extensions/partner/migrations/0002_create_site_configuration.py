# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0001_squashed_0008_auto_20150914_1057'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='partner',
            options={'verbose_name': 'Partner', 'verbose_name_plural': 'Partners'},
        ),
    ]
