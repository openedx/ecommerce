# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.loading import get_model

ProductAttribute = get_model("catalogue", "ProductAttribute")


def alter_couponvouchers_attribute(apps, schema_editor):
    """Change the coupon_vouchers product attribute to be required."""
    ProductAttribute.skip_history_when_saving = True
    coupon_vouchers = ProductAttribute.objects.get(code='coupon_vouchers')
    coupon_vouchers.required = True
    coupon_vouchers.save()


def reverse_migration(apps, schema_editor):
    """Reverse coupon_vouchers product attribute to not be required."""
    ProductAttribute.skip_history_when_saving = True
    coupon_vouchers = ProductAttribute.objects.get(code='coupon_vouchers')
    coupon_vouchers.required = False
    coupon_vouchers.save()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0013_coupon_product_class')
    ]
    operations = [
        migrations.RunPython(alter_couponvouchers_attribute, reverse_migration)
    ]
