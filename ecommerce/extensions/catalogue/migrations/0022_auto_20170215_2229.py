# -*- coding: utf-8 -*-


import oscar.models.fields.slugfield
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0021_auto_20170215_2224'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='slug',
            field=oscar.models.fields.slugfield.SlugField(max_length=255, verbose_name='Slug'),
        ),
    ]
