# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_siteconfiguration_payment_support_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='payment_support_url',
            field=models.CharField(help_text='URL for payment support issues.', max_length=255, verbose_name='Payment support url', blank=True),
        ),
    ]
