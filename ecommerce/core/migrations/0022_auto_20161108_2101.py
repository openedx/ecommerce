# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_siteconfiguration_client_side_payment_processor'),
    ]

    operations = [
        migrations.AlterField(
            model_name='siteconfiguration',
            name='client_side_payment_processor',
            field=models.CharField(help_text='Processor that will be used for client-side payments', max_length=255, null=True, verbose_name='Client-side payment processor', blank=True),
        ),
    ]
