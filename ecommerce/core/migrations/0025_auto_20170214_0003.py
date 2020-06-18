# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_auto_20170208_1520'),
    ]

    operations = [
        migrations.AlterField(
            model_name='siteconfiguration',
            name='sdn_api_list',
            field=models.CharField(help_text='A comma-separated list of Treasury OFAC lists to check against.', max_length=255, verbose_name='SDN lists', blank=True),
        ),
    ]
