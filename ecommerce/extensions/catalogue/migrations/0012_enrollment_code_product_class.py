# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import oscar
from django.db import models, migrations


def create_product_class(apps, schema_editor):
    """
    Create a default EnrollmentCode class with added attributes:
        - catalog (of courses)
        - start date (of validity)
        - end date
    """
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


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0011_auto_20151019_0639')
    ]
    operations = [
        migrations.RunPython(create_product_class)
    ]