# -*- coding: utf-8 -*-


import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0001_initial'),
        ('basket', '0005_auto_20150709_1205'),
    ]

    operations = [
        migrations.AddField(
            model_name='basket',
            name='site',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, default=None, blank=True, to='sites.Site', null=True, verbose_name='Site'),
        ),
    ]
