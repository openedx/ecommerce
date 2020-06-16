# -*- coding: utf-8 -*-


import oscar.models.fields.slugfield
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0008_auto_20170215_2224'),
    ]

    operations = [
        migrations.AlterField(
            model_name='line',
            name='line_reference',
            field=oscar.models.fields.slugfield.SlugField(max_length=128, verbose_name='Line Reference'),
        ),
    ]
