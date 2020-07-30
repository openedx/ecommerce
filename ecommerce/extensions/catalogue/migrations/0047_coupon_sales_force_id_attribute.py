# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME


def create_sales_force_id_attribute(apps, schema_editor):
    """Create coupon sales_force_id attribute."""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    ProductAttribute.skip_history_when_saving = True

    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    pa = ProductAttribute(
        product_class=coupon,
        name='Sales Force ID',
        code='sales_force_id',
        type='text',
        required=False
    )
    pa.save()


def remove_sales_force_id_attribute(apps, schema_editor):
    """Remove coupon sales_force_id attribute."""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)

    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.get(product_class=coupon, code='sales_force_id').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0046_coupon_inactive_attribute')
    ]
    operations = [
        migrations.RunPython(create_sales_force_id_attribute, remove_sales_force_id_attribute)
    ]
