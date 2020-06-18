# -*- coding: utf-8 -*-


from django.db import migrations


def create_sample(apps, schema_editor):
    """
    Create the async_order_fulfillment sample if it does not already exist, and
    delete the existing switch with the same name.
    """
    Sample = apps.get_model('waffle', 'Sample')
    Sample.objects.get_or_create(
        name='async_order_fulfillment',
        defaults={
            'percent': 0.0,
            'note': 'Determines what percentage of orders are fulfilled asynchronously.',
        }
    )

    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.filter(name='async_order_fulfillment').delete()


def delete_sample(apps, schema_editor):
    """
    Delete the async_order_fulfillment sample, and create the old switch with
    the same name.
    """
    Sample = apps.get_model('waffle', 'Sample')
    Sample.objects.filter(name='async_order_fulfillment').delete()

    Switch = apps.get_model('waffle', 'Switch')
    Switch.objects.get_or_create(name='async_order_fulfillment', defaults={'active': False})


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0009_service_user_privileges'),
        ('waffle', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_sample, delete_sample),
    ]
