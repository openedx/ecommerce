# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from __future__ import absolute_import
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_auto_20150914_1120'),
    ]

    operations = [
        migrations.AlterField(
            model_name='siteconfiguration',
            name='site',
            field=models.OneToOneField(to='sites.Site'),
        ),
    ]
