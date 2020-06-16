# -*- coding: utf-8 -*-


from django.conf import settings
from django.db import migrations

from ecommerce.core.constants import ENROLLMENT_CODE_SWITCH


def create_switch(apps, schema_editor):
    """Create a switch for automatic creation of enrollment code products."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name=ENROLLMENT_CODE_SWITCH, defaults={'active': False})


def remove_switch(apps, schema_editor):
    """Remove enrollment code switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name=ENROLLMENT_CODE_SWITCH).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('core', '0013_siteconfiguration_segment_key')
    ]
    operations = [
        migrations.RunPython(create_switch, remove_switch)
    ]
