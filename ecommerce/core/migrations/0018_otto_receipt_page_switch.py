# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def create_switch(apps, schema_editor):
    """Create a switch for using the Otto-hosted receipt page."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='otto_receipt_page', defaults={'active': False})


def remove_switch(apps, schema_editor):
    """Remove Otto receipt page switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='otto_receipt_page').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_siteconfiguration_payment_support_email'),
        ('waffle', '0001_initial')
    ]
    operations = [
        migrations.RunPython(create_switch, remove_switch)
    ]
