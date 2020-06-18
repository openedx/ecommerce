# -*- coding: utf-8 -*-


import oscar.models.fields
from django.db import migrations, models


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
