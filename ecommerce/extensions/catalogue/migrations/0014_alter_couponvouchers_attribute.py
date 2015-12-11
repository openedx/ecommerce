# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from oscar.core.loading import get_model

ProductAttribute = get_model("catalogue", "ProductAttribute")


def alter_couponvouchers_attribute(apps, shema_editor):

    coupon_vouchers = ProductAttribute.objects.get(code='coupon_vouchers')
    coupon_vouchers.required = True
    coupon_vouchers.save()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0013_coupon_product_class')
    ]
    operations = [
        migrations.RunPython(alter_couponvouchers_attribute)
    ]
