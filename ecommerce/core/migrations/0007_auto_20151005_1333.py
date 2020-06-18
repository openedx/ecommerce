# -*- coding: utf-8 -*-


from django.db import migrations


def create_switch(apps, schema_editor):
    """Create the async_order_fulfillment switch if it does not already exist."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='async_order_fulfillment', defaults={'active': False})


def delete_switch(apps, schema_editor):
    """Delete the async_order_fulfillment switch."""
    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='async_order_fulfillment').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0006_add_service_user'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_switch, reverse_code=delete_switch),
    ]
