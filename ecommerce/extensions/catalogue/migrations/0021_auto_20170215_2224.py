# -*- coding: utf-8 -*-


import django.core.validators
import oscar.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0020_auto_20161025_1446'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productattribute',
            name='code',
            field=models.SlugField(max_length=128, verbose_name='Code', validators=[django.core.validators.RegexValidator(regex=b'^[a-zA-Z_][0-9a-zA-Z_]*$', message="Code can only contain the letters a-z, A-Z, digits, and underscores, and can't start with a digit."), oscar.core.validators.non_python_keyword]),
        ),
        migrations.AlterUniqueTogether(
            name='attributeoption',
            unique_together=set([('group', 'option')]),
        ),
    ]
