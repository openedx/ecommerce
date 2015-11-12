# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import oscar
from django.db import models, migrations


def create_product_class(apps, schema_editor):
    """
    Create a default EnrollmentCode class with added attributes:
        - catalog (of courses)
        - client
        - start date (of validity)
        - end date
        - type
    """
    AttributeOptionGroup = apps.get_model("catalogue", "AttributeOptionGroup")
    AttributeOption = apps.get_model("catalogue", "AttributeOption")
    Category = apps.get_model("catalogue", "Category")
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    # Create a new product class for enrollment codes
    enrollment_code = ProductClass.objects.create(
        track_stock=False,
        requires_shipping=False,
        name='Enrollment code',
        slug='enrollment_code',
    )

    # Create product attributes for enrollment code products
    ProductAttribute.objects.create(
        product_class=enrollment_code,
        name="Catalog",
        code="catalog",
        type="entity",
        required=True
    )
    ProductAttribute.objects.create(
        product_class=enrollment_code,
        name="Client",
        code="client",
        type="entity",
        required=True
    )
    ProductAttribute.objects.create(
        product_class=enrollment_code,
        name="Start date",
        code="start_date",
        type="date",
        required=True
    )
    ProductAttribute.objects.create(
        product_class=enrollment_code,
        name="End date",
        code="end_date",
        type="date",
        required=True
    )

    # Option group for the type of enrollment code.
    # single_use - Can be used once by one customer
    # multi_use - Can be used multiple times by multiple customers
    # once_per_customer - Can only be used once per customer
    group = AttributeOptionGroup.objects.create(
        name="Type"
    )
    AttributeOption.objects.create(
        group=group,
        option='Single use'
    )
    AttributeOption.objects.create(
        group=group,
        option='Multi-use'
    )
    AttributeOption.objects.create(
        group=group,
        option='Once per customer'
    )

    ProductAttribute.objects.create(
        product_class=enrollment_code,
        name="Type",
        code="type",
        type="option",
        option_group=group,
        required=True
    )

    # Create a category for course seats
    Category.objects.create(
        description="All Enrollment Codes",
        numchild=2,
        slug="enrollment_codes",
        depth=1,
        path="0002",
        image="",
        name="Enrollment Codes"
    )


def remove_product_class(apps, schema_editor):
    """ Reverse function. """
    Category = apps.get_model("catalogue", "Category")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    Category.objects.filter(slug='enrollment_code').delete()
    ProductClass.objects.filter(slug='enrollment_code').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0011_auto_20151019_0639')
    ]
    operations = [
        migrations.RunPython(create_product_class, remove_product_class)
    ]
