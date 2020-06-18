# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_siteconfiguration_payment_support_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='siteconfiguration',
            name='affiliate_cookie_name',
            field=models.CharField(default=b'', help_text='Name of cookie storing affiliate data.', max_length=255, verbose_name='Affiliate Cookie Name', blank=True),
        ),
        migrations.AddField(
            model_name='siteconfiguration',
            name='utm_cookie_name',
            field=models.CharField(default=b'', help_text='Name of cookie storing UTM data.', max_length=255, verbose_name='UTM Cookie Name', blank=True),
        ),
    ]
