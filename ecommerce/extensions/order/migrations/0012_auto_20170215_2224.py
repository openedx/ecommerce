# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0011_auto_20161025_1446'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='line',
            options={'ordering': ['pk'], 'verbose_name': 'Order Line', 'verbose_name_plural': 'Order Lines'},
        ),
    ]
