# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


def create_catalog(apps, schema_editor):
    """

    Create all the Product Types, Products, Attributes, Categories, and other data models we need out of the
    box for the EdX Catalog. This data migration will create the "Seat" type, along with our
    default product, a DemoX Course and Seat with an Honor Certificate.

    """
    # Create all our Product Types.
    ProductClass = apps.get_model("catalogue", "ProductClass")
    seat = ProductClass(track_stock=False, requires_shipping=False, name='Seat', slug='seat')
    seat.save()

    # Create our Product Attributes
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    course_key = ProductAttribute(product_class=seat, name="course_key", code="course_key", type="text", required=True)
    course_key.save()
    id_verification_required = ProductAttribute(
        product_class=seat,
        name="id_verification_required",
        code="id_verification_required",
        type="boolean",
        required=False
    )
    id_verification_required.save()
    certificate_type = ProductAttribute(
        product_class=seat,
        name="certificate_type",
        code="certificate_type",
        type="text",
        required=False
    )
    certificate_type.save()

    # Create all the categories associated with our Product Types.
    Category = apps.get_model("catalogue", "Category")
    seats = Category(
        description="All Course Seats.",
        numchild=1,
        slug="seats",
        depth=1,
        full_name="Course Seats",
        path="0001",
        image="",
        name="Seats"
    )
    seats.save()

    # Define our Product, DemoX, with its one child product, the Seat in DemoX with an Honor Cert.
    Product = apps.get_model("catalogue", "Product")
    demox = Product(
        description="",
        title="EdX DemoX Course Seat",
        upc="000000000001",
        is_discountable=True,
        slug="edx-demox-course",
        structure='parent',
        product_class=seat
    )
    demox.save()
    honor_seat = Product(
        description="",
        parent=demox,
        title="Seat in DemoX Course with Honor Certificate",
        upc="000000000002",
        is_discountable=True,
        slug="edx-demox-course-seat-honor",
        structure='child'
    )
    honor_seat.save()

    # ProductCategory defines the association of a category with a Product.
    ProductCategory = apps.get_model("catalogue", "ProductCategory")
    seats_category = ProductCategory(category=seats, product=demox)
    seats_category.save()
    # Define the product attributes for DemoX.
    ProductAttributeValue = apps.get_model("catalogue", "ProductAttributeValue")
    demox_course_key = ProductAttributeValue(attribute=course_key, product=demox, value_text="edX/DemoX/Demo_Course")
    demox_course_key.save()
    demox_is_verified = ProductAttributeValue(
        attribute=id_verification_required, product=honor_seat, value_boolean=False
    )
    demox_is_verified.save()
    demox_honor = ProductAttributeValue(attribute=certificate_type, product=honor_seat, value_text="honor")
    demox_honor.save()
    demox_honor_course_key = ProductAttributeValue(
        attribute=course_key,
        product=honor_seat,
        value_text="edX/DemoX/Demo_Course"
    )
    demox_honor_course_key.save()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_catalog),
    ]
