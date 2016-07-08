# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_siteconfiguration_from_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='order_attribution_period',
            field=models.PositiveIntegerField(default=60, help_text='Number of days after an order is placed before it can be attributed to an affiliate.', verbose_name='Order Attribution Period'),
        ),
    ]
