# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME


def create_contract_metadata_attribute(apps, schema_editor):
    """Create coupon enterprise_contract_metadata attribute."""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    ProductAttribute.skip_history_when_saving = True
    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    pa = ProductAttribute(
        product_class=coupon,
        name='Enterprise Contract Metadata',
        code='enterprise_contract_metadata',
        type='entity',
        required=False
    )
    pa.save()


def remove_contract_metadata_attribute(apps, schema_editor):
    """Remove coupon enterprise_contract_metadata attribute."""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.get(product_class=coupon, code='enterprise_contract_metadata').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0043_auto_20191115_2151')
    ]
    operations = [
        migrations.RunPython(create_contract_metadata_attribute, remove_contract_metadata_attribute)
    ]
