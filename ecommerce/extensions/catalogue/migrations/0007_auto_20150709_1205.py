# -*- coding: utf-8 -*-


import django.core.validators
import django.db.models.deletion
import oscar.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0006_credit_provider_attr'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ['path'], 'verbose_name': 'Category', 'verbose_name_plural': 'Categories'},
        ),
        migrations.RemoveField(
            model_name='category',
            name='full_name',
        ),
        migrations.AlterField(
            model_name='category',
            name='slug',
            field=models.SlugField(max_length=255, verbose_name='Slug'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='product',
            name='product_class',
            field=models.ForeignKey(related_name='products', on_delete=django.db.models.deletion.PROTECT, blank=True, to='catalogue.ProductClass', help_text='Choose what type of product this is', null=True, verbose_name='Product type'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='productattribute',
            name='code',
            field=models.SlugField(max_length=128, verbose_name='Code', validators=[django.core.validators.RegexValidator(regex=b'^[a-zA-Z_][0-9a-zA-Z_]*$', message="Code can only contain the letters a-z, A-Z, digits, and underscores, and can't start with a digit"), oscar.core.validators.non_python_keyword]),
            preserve_default=True,
        ),
    ]
