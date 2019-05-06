# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from oscar.core.loading import get_model
from oscar.core.utils import slugify

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME

Category = get_model("catalogue", "Category")
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def create_product_class(apps, schema_editor):
    """ Create a course entitlement product class """
    # Create a new product class for course entitlement
    course_entitlement = ProductClass(
        track_stock=False,
        requires_shipping=False,
        name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
        slug=slugify(COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)
    )
    course_entitlement.save_without_historical_record()

    # Create product attributes for course entitlement products
    pa1 = ProductAttribute(
        product_class=course_entitlement,
        name="course_key",
        code="course_key",
        type="text",
        required=True
    )
    pa1.save_without_historical_record()

    pa2 = ProductAttribute(
        product_class=course_entitlement,
        name="certificate_type",
        code="certificate_type",
        type="text",
        required=False
    )
    pa2.save_without_historical_record()

    # Create a category for course entitlements
    Category.skip_history_when_saving = True
    Category.add_root(
        description="All course entitlements",
        slug="course_entitlements",
        image="",
        name="Course Entitlements"
    )


def remove_product_class(apps, schema_editor):
    """ Reverse function. """
    Product.skip_history_when_saving = True
    Category.skip_history_when_saving = True
    ProductClass.skip_history_when_saving = True

    # For cascading delete
    ProductAttribute.skip_history_when_saving = True

    Product.objects.filter(product_class=ProductClass.objects.get(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)).delete()
    Category.objects.filter(slug='course_entitlements').delete()
    ProductClass.objects.filter(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0024_fix_enrollment_code_slug')
    ]

    operations = [
        migrations.RunPython(create_product_class, remove_product_class),
    ]
