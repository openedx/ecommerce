# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.core.constants import HUBSPOT_FORMS_INTEGRATION_ENABLE


def create_switch(apps, schema_editor):
    """Create and activate the 'hubspot_forms_integration_enable' switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name=HUBSPOT_FORMS_INTEGRATION_ENABLE, defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the 'hubspot_forms_integration_enable' switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=HUBSPOT_FORMS_INTEGRATION_ENABLE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]
