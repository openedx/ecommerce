# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0014_sdncheckfailure_site'),
    ]

    operations = [
        migrations.AlterField(
            model_name='source',
            name='reference',
            field=models.CharField(max_length=255, verbose_name='Reference', blank=True),
        ),
    ]
