# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_siteconfiguration_enable_otto_receipt_page'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='client_side_payment_processor',
            field=models.CharField(help_text='Processor that will be used for client-side payments', max_length=255, null=True, verbose_name='Payment processors', blank=True),
        ),
    ]
