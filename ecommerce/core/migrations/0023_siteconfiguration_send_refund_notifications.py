# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_auto_20161108_2101'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='send_refund_notifications',
            field=models.BooleanField(default=False, verbose_name='Send refund email notification'),
        ),
    ]
