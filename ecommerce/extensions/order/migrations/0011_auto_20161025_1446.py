# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0010_auto_20160529_2245'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='order',
            options={'ordering': ['-date_placed'], 'verbose_name': 'Order', 'verbose_name_plural': 'Orders'},
        ),
    ]
