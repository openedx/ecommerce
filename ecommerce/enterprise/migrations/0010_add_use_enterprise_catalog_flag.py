# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.enterprise.constants import USE_ENTERPRISE_CATALOG


def create_flag(apps, schema_editor):
    """Create the `use_enterprise_catalog` flag if it does not already exist."""
    Flag = apps.get_model('waffle', 'Flag')
    Flag.objects.get_or_create(
        name=USE_ENTERPRISE_CATALOG,
        defaults={'everyone': None, 'superusers': False},
    )


def delete_flag(apps, schema_editor):
    """Delete the `use_enterprise_catalog` flag if one exists."""
    Flag = apps.get_model('waffle', 'Flag')
    Flag.objects.filter(name=USE_ENTERPRISE_CATALOG).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('enterprise', '0009_remove_enterprise_offers_for_coupons'),
    ]

    operations = [
        migrations.RunPython(create_flag, delete_flag)
    ]
