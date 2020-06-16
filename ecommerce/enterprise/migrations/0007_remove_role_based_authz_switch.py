# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.enterprise.constants import USE_ROLE_BASED_ACCESS_CONTROL


def create_switch(apps, schema_editor):
    """Create the `use_role_based_access_control` switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.update_or_create(name=USE_ROLE_BASED_ACCESS_CONTROL, defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the `use_role_based_access_control` switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=USE_ROLE_BASED_ACCESS_CONTROL).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0006_add_role_based_authz_switch'),
    ]

    operations = [
        migrations.RunPython(delete_switch, create_switch)
    ]
