# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def create_switch(apps, schema_editor):
    """Create and activate the sailthru_enable switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='sailthru_edx_only', defaults={'active': True})


def delete_switch(apps, schema_editor):
    """Delete the sailthru_enable switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='sailthru_edx_only').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('sailthru', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]
