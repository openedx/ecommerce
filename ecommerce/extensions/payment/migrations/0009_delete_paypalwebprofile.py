# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0008_remove_cybersource_level23_sample'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PaypalWebProfile',
        ),
    ]
