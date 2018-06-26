# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations

from ecommerce.core.constants import BACKOFF_FOR_API_CALLS_SWITCH


def create_switch(apps, schema_editor):
    """Create a switch for backoff and retry of api calls."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name=BACKOFF_FOR_API_CALLS_SWITCH, defaults={'active': False})


def remove_switch(apps, schema_editor):
    """Remove backoff for api calls switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=BACKOFF_FOR_API_CALLS_SWITCH).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_auto_20180510_0823'),
    ]
    operations = [
        migrations.RunPython(create_switch, remove_switch)
    ]
