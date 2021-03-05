from django.db import migrations

from ecommerce.core.constants import ENABLE_BRAZE


def create_switch(apps, schema_editor):
    """Create the `enable_braze` switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.update_or_create(name=ENABLE_BRAZE, defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the `enable_braze` switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=ENABLE_BRAZE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0062_siteconfiguration_account_microfrontend_url'),
    ]

    operations = [
        migrations.RunPython(create_switch, delete_switch),
    ]
