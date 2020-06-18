# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('basket', '0007_auto_20160907_2040'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='line',
            options={'ordering': ['date_created', 'pk'], 'verbose_name': 'Basket line', 'verbose_name_plural': 'Basket lines'},
        ),
    ]
