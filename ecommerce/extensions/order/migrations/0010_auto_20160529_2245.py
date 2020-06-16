# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0009_auto_20150709_1205'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='order',
            options={'ordering': ['-date_placed'], 'get_latest_by': 'date_placed', 'verbose_name': 'Order', 'verbose_name_plural': 'Orders'},
        ),
    ]
