# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from oscar.core.utils import slugify

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME


def create_catalog(apps, schema_editor):
    """

    Create all the Product Types, Products, Attributes, Categories, and other data models we need out of the
    box for the EdX Catalog. This data migration will create the "Seat" type, along with our
    default product, a DemoX Course and Seat with an Honor Certificate.

    """
    Category = apps.get_model("catalogue", "Category")
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    # Create a new product class for course seats
    seat = ProductClass.objects.create(
        track_stock=False,
        requires_shipping=False,
        name=SEAT_PRODUCT_CLASS_NAME,
        slug=slugify(SEAT_PRODUCT_CLASS_NAME)
    )

    # Create product attributes for course seat products
    ProductAttribute.objects.create(
        product_class=seat,
        name="course_key",
        code="course_key",
        type="text",
        required=True
    )
    ProductAttribute.objects.create(
        product_class=seat,
        name="id_verification_required",
        code="id_verification_required",
        type="boolean",
        required=False
    )
    ProductAttribute.objects.create(
        product_class=seat,
        name="certificate_type",
        code="certificate_type",
        type="text",
        required=False
    )

    # Create a category for course seats
    Category.objects.create(
        description="All course seats",
        numchild=1,
        slug="seats",
        depth=1,
        full_name="Course Seats",
        path="0001",
        image="",
        name="Seats"
    )


def remove_catalog(apps, schema_editor):
    """ Reverse function. """
    Category = apps.get_model("catalogue", "Category")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    Category.objects.filter(slug='seats').delete()
    ProductClass.objects.filter(name=SEAT_PRODUCT_CLASS_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_catalog, remove_catalog),
    ]
