# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models

from extensions.payment.processors.adyen import Adyen


def enable_adyen_payment_processor(apps, schema_editor):
    """
    Enable both existing payment processors.
    """
    Switch = apps.get_model('waffle', 'Switch')
    Switch(name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + Adyen.NAME, active=True).save()


def delete_adyen_processor_switch(apps, schema_editor):
    """
    Remove payment processor switches.
    """
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get(name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + Adyen.NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0006_enable_payment_processors'),
    ]

    operations = [
        migrations.RunPython(enable_adyen_payment_processor, delete_adyen_processor_switch)
    ]
