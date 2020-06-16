# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_auto_20161012_1404'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='enable_otto_receipt_page',
            field=models.BooleanField(default=False, help_text='Enable the usage of Otto receipt page.', verbose_name='Enable Otto receipt page'),
        ),
    ]
