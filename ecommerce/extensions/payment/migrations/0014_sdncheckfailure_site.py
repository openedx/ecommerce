# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0001_initial'),
        ('payment', '0013_sdncheckfailure'),
    ]

    operations = [
        migrations.AddField(
            model_name='sdncheckfailure',
            name='site',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, verbose_name='Site', blank=True, to='sites.Site', null=True),
        ),
    ]
