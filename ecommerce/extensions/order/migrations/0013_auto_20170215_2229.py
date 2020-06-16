# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0012_auto_20170215_2224'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalorder',
            name='guest_email',
            field=models.EmailField(max_length=254, verbose_name='Guest email address', blank=True),
        ),
        migrations.AlterField(
            model_name='order',
            name='guest_email',
            field=models.EmailField(max_length=254, verbose_name='Guest email address', blank=True),
        ),
    ]
