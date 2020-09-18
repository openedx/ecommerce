# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.loading import get_model

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME

ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def create_is_public_code_attribute(apps, schema_editor):
    """Create coupon is_public_code attribute."""
    ProductAttribute.skip_history_when_saving = True

    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    product_attribute = ProductAttribute(
        product_class=coupon,
        name='Is Public Code?',
        code='is_public_code',
        type='boolean',
        required=False
    )
    product_attribute.save()


def remove_is_public_code_attribute(apps, schema_editor):
    """Remove coupon is_public_code attribute."""
    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)

    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.get(product_class=coupon, code='is_public_code').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0050_add_b2b_affiliate_promotion_coupon_category')
    ]
    operations = [
        migrations.RunPython(create_is_public_code_attribute, remove_is_public_code_attribute)
    ]
