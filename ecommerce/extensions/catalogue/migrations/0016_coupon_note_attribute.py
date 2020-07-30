# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME


def create_note_attribute(apps, schema_editor):
    """Create coupon note attribute."""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    ProductAttribute.skip_history_when_saving = True
    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    ProductAttribute.objects.create(
        product_class=coupon,
        name='Note',
        code='note',
        type='text',
        required=False
    )


def remove_note_attribute(apps, schema_editor):
    """Remove coupon note attribute."""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    ProductAttribute.skip_history_when_saving = True
    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    ProductAttribute.objects.get(product_class=coupon, name='Note').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0015_default_categories')
    ]
    operations = [
        migrations.RunPython(create_note_attribute, remove_note_attribute)
    ]
