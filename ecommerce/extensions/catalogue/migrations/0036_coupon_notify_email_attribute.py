# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.loading import get_model

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME

ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def create_notify_email_attribute(apps, schema_editor):
    """Create coupon notify_email attribute."""
    ProductAttribute.skip_history_when_saving = True

    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)
    pa = ProductAttribute(
        product_class=coupon,
        name='Notification Email',
        code='notify_email',
        type='text',
        required=False
    )
    pa.save()


def remove_notify_email_attribute(apps, schema_editor):
    """Remove coupon notify_email attribute."""
    coupon = ProductClass.objects.get(name=COUPON_PRODUCT_CLASS_NAME)

    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.get(product_class=coupon, code='notify_email').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0035_add_partner_no_rev_coupon_categories')
    ]
    operations = [
        migrations.RunPython(create_notify_email_attribute, remove_notify_email_attribute)
    ]
