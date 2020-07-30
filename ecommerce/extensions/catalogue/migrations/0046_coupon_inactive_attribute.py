# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME


def create_inactive_attribute(apps, schema_editor):
    """Create coupon inactive attribute."""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    ProductAttribute.skip_history_when_saving = True

    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    product_attribute = ProductAttribute(
        product_class=coupon,
        name='Inactive',
        code='inactive',
        type=ProductAttribute.BOOLEAN,
        required=False
    )
    product_attribute.save()


def remove_inactive_attribute(apps, schema_editor):
    """Remove coupon inactive attribute."""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)

    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.get(product_class=coupon, code='inactive').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0045_add_edx_employee_coupon_category')
    ]
    operations = [
        migrations.RunPython(create_inactive_attribute, remove_inactive_attribute)
    ]
