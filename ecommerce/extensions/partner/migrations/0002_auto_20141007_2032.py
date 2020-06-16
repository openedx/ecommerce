# -*- coding: utf-8 -*-


import oscar.core.utils
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockrecord',
            name='price_currency',
            field=models.CharField(default=oscar.core.utils.get_default_currency, max_length=12, verbose_name='Currency'),
        ),
    ]
