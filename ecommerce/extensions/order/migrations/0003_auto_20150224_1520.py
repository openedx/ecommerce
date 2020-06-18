# -*- coding: utf-8 -*-


from django.db import migrations, models


def create_shipping_event(apps, schema_editor):
    """

    Create a single new shipping event type that can be applied to an order. This will allow us to initiate order
    shipment.

    """
    # Create all our Product Types.
    ShippingEventType = apps.get_model("order", "ShippingEventType")
    ShippingEventType.objects.create(code="shipped", name="Shipped")


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0002_auto_20141007_2032'),
    ]

    operations = [
        migrations.RunPython(create_shipping_event),
    ]
