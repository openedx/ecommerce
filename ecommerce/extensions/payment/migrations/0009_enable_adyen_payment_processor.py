# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations

from ecommerce.extensions.payment.processors.adyen import Adyen


def enable_payment_processor(apps, schema_editor):
    """
    Enable Adyen payment processor.
    """
    Switch = apps.get_model('waffle', 'Switch')
    Switch(name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + Adyen.NAME, active=True).save()


def delete_processor_switch(apps, schema_editor):
    """
    Remove Adyen payment processor switch.
    """
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get(name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + Adyen.NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0008_remove_cybersource_level23_sample'),
    ]

    operations = [
        migrations.RunPython(enable_payment_processor, delete_processor_switch)
    ]
