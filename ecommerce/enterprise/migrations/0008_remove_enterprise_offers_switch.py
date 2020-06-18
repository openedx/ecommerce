# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.enterprise.constants import ENTERPRISE_OFFERS_SWITCH


def create_switch(apps, schema_editor):
    """Create the `enable_enterprise_offers` switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.update_or_create(name=ENTERPRISE_OFFERS_SWITCH, defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the `enable_enterprise_offers` switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=ENTERPRISE_OFFERS_SWITCH).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0007_remove_role_based_authz_switch'),
    ]

    operations = [
        migrations.RunPython(delete_switch, create_switch)
    ]
