# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import oscar.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('offer', '0009_range_enterprise_customer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='benefit',
            name='proxy_class',
            field=oscar.models.fields.NullCharField(default=None, max_length=255, verbose_name='Custom class'),
        ),
    ]
