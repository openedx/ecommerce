# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0008_auto_20150914_1057'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='enable_sailthru',
            field=models.BooleanField(default=True, help_text='Report purchases/enrolls to Sailthru.', verbose_name='Enable Sailthru Reporting'),
        ),
    ]
