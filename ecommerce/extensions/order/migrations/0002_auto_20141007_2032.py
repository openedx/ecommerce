# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
import oscar.core.utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='currency',
            field=models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency'),
        ),
    ]
