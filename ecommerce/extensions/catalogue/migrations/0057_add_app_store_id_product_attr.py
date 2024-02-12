# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.loading import get_model

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME

ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def create_app_store_id_attribute(apps, schema_editor):
    """Create seat App Store Id attribute."""
    ProductAttribute.skip_history_when_saving = True

    seat = ProductClass.objects.get(name=SEAT_PRODUCT_CLASS_NAME)
    product_attribute = ProductAttribute(
        product_class=seat,
        name='App Store Id',
        code='app_store_id',
        type='text',
        required=False
    )
    product_attribute.save()


def remove_app_store_id_attribute(apps, schema_editor):
    """Remove seat App Store Id attribute."""
    seat = ProductClass.objects.get(name=SEAT_PRODUCT_CLASS_NAME)

    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.get(product_class=seat, code='app_store_id').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0056_add_variant_id_seat_product_attr')
    ]
    operations = [
        migrations.RunPython(create_app_store_id_attribute, remove_app_store_id_attribute)
    ]
