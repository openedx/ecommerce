# -*- coding: utf-8 -*-


from django.conf import settings
from django.db import migrations


def create_switch(apps, schema_editor):
    """Create the `enable_enterprise_on_runtime` switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.update_or_create(name=settings.ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH, defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the `enable_enterprise_on_runtime` switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=settings.ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0002_add_enterprise_offers_switch'),
    ]

    operations = [
        migrations.RunPython(create_switch, delete_switch)
    ]
