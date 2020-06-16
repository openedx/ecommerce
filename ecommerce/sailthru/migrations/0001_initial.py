# -*- coding: utf-8 -*-


from django.db import migrations


def create_switch(apps, schema_editor):
    """Create and activate the sailthru_enable switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='sailthru_enable', defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the sailthru_enable switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='sailthru_enable').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]
