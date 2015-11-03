# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0004_auto_20150803_1406'),
        ('catalogue', '0012_enrollment_code_product_class'),
    ]

    operations = [
        migrations.AddField(
            model_name='catalog',
            name='courses',
            field=models.ManyToManyField(to='courses.Course', blank=True),
        ),
    ]
