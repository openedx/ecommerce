# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_siteconfiguration_enable_enrollment_codes'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='siteconfiguration',
            name='payment_processors',
        ),
        migrations.RemoveField(
            model_name='siteconfiguration',
            name='theme_scss_path',
        ),
        migrations.AddField(
            model_name='siteconfiguration',
            name='basket_layout',
            field=models.CharField(default=b'single_column', help_text='The layout of the basket page.', max_length=16, verbose_name='Basket Page Layout', choices=[(b'single_column', 'Single Column'), (b'two_column', 'Two Column')]),
        ),
        migrations.AddField(
            model_name='siteconfiguration',
            name='checkout_template',
            field=models.CharField(default=b'checkout/_two_page.html', help_text='The template to use for checkout.', max_length=255, verbose_name='Checkout Template', choices=[(b'checkout/_two_page.html', b'Two Page')]),
        ),
    ]
