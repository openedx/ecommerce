# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0002_auto_20160517_0930'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productalert',
            name='email',
            field=models.EmailField(db_index=True, max_length=254, verbose_name='Email', blank=True),
        ),
    ]
