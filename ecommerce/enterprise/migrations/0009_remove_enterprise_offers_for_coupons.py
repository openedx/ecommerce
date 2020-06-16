# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.enterprise.constants import ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH


def create_switch(apps, schema_editor):
    """Create the `enable_enterprise_on_runtime` switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.update_or_create(name=ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH, defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the `enable_enterprise_on_runtime` switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0008_remove_enterprise_offers_switch'),
    ]

    operations = [
        migrations.RunPython(delete_switch, create_switch)
    ]
