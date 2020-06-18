# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.loading import get_model
from oscar.core.utils import slugify

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME

Category = get_model("catalogue", "Category")
ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def create_product_class(apps, schema_editor):
    """Create a Coupon product class."""
    for klass in (Category, ProductAttribute, ProductClass):
        klass.skip_history_when_saving = True

    coupon = ProductClass(
        track_stock=False,
        requires_shipping=False,
        name=COUPON_PRODUCT_CLASS_NAME,
        slug=slugify(COUPON_PRODUCT_CLASS_NAME),
    )
    coupon.save()

    pa = ProductAttribute(
        product_class=coupon,
        name='Coupon vouchers',
        code='coupon_vouchers',
        type='entity',
        required=False
    )
    pa.save()

    # Create a category for coupons.
    c = Category(
        description='All Coupons',
        slug='coupons',
        depth=1,
        path='0002',
        image='',
        name='Coupons'
    )
    c.save()


def remove_product_class(apps, schema_editor):
    """ Reverse function. """
    ProductClass.skip_history_when_saving = True
    Category.objects.filter(slug='coupon').delete()
    ProductClass.objects.filter(name=COUPON_PRODUCT_CLASS_NAME).delete()


def remove_enrollment_code(apps, schema_editor):
    """ Removes the enrollment code product and it's attributes. """
    ProductClass.skip_history_when_saving = True
    Category.objects.filter(slug='enrollment_codes').delete()
    ProductClass.objects.filter(slug='enrollment_code').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0012_enrollment_code_product_class')
    ]
    operations = [
        migrations.RunPython(remove_enrollment_code),
        migrations.RunPython(create_product_class, remove_product_class)
    ]
