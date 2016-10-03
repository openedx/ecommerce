# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0011_auto_20161025_1446'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='historicalorder',
            options={'ordering': ('-history_date', '-history_id'), 'get_latest_by': 'history_date', 'verbose_name': 'historical order'},
        ),
        migrations.AlterModelOptions(
            name='order',
            options={'get_latest_by': 'date_placed'},
        ),
    ]
