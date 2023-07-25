# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.loading import get_model

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME

ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")

SF_LINE_ITEM_ATTRIBUTE_CODE = 'salesforce_opportunity_line_item'


def create_sf_opp_line_item_attribute(apps, schema_editor):
    """Create enterprise coupon salesforce_opportunity_line_item product attribute."""
    ProductAttribute.skip_history_when_saving = True
    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    pa = ProductAttribute(
        product_class=coupon,
        name='Salesforce Opportunity Line Item',
        code=SF_LINE_ITEM_ATTRIBUTE_CODE,
        type='text',
        required=True,
    )
    pa.save()


def remove_sf_opp_line_item_attribute(apps, schema_editor):
    """Remove enterprise coupon salesforce_opportunity_line_item product attribute."""
    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.get(product_class=coupon, code=SF_LINE_ITEM_ATTRIBUTE_CODE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0054_add_variant_id_product_attr')
    ]
    operations = [
        migrations.RunPython(
            create_sf_opp_line_item_attribute,
            remove_sf_opp_line_item_attribute,
        ),
    ]
