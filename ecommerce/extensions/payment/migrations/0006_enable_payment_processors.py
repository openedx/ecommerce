# -*- coding: utf-8 -*-


from django.conf import settings
from django.db import migrations, models

from ecommerce.extensions.payment.processors.cybersource import Cybersource
from ecommerce.extensions.payment.processors.paypal import Paypal


def enable_payment_processors(apps, schema_editor):
    """
    Enable both existing payment processors.
    """
    Switch = apps.get_model('waffle', 'Switch')
    for processor in (Cybersource, Paypal):
        Switch(name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + processor.NAME, active=True).save()


def delete_processor_switches(apps, schema_editor):
    """
    Remove payment processor switches.
    """
    Switch = apps.get_model('waffle', 'Switch')
    for processor in (Cybersource, Paypal):
        Switch.objects.get(name=settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + processor.NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0005_paypalwebprofile'),
    ]

    operations = [
        migrations.RunPython(enable_payment_processors, delete_processor_switches)
    ]
