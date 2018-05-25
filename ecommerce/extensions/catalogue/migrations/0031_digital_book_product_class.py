# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from oscar.core.loading import get_model
from oscar.core.utils import slugify

from ecommerce.core.constants import DIGITAL_BOOK_PRODUCT_CLASS_NAME

Category = get_model("catalogue", "Category")
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")
DIGITAL_BOOK_SLUG_NAME = slugify(DIGITAL_BOOK_PRODUCT_CLASS_NAME)


def create_product_class(apps, schema_editor):
    """ Create a digital book product class """

    # Create a new product class for digital book
    digital_book = ProductClass.objects.create(
        track_stock=False,
        requires_shipping=False,
        name=DIGITAL_BOOK_PRODUCT_CLASS_NAME,
        slug=DIGITAL_BOOK_SLUG_NAME
    )

    # Create product attributes for digital book products
    ProductAttribute.objects.create(
        product_class=digital_book,
        name="book_key",
        code="book_key",
        type="text",
        required=True
    )

    # Create a category for the digital book
    Category.add_root(
        description="All digital books",
        slug="digital_books",
        image="",
        name="Digital Books"
    )


def remove_product_class(apps, schema_editor):
    """ Reverse function. """
    Product.objects.filter(product_class=ProductClass.objects.get(name=DIGITAL_BOOK_PRODUCT_CLASS_NAME)).delete()
    Category.objects.filter(slug=DIGITAL_BOOK_SLUG_NAME).delete()
    ProductClass.objects.filter(name=DIGITAL_BOOK_PRODUCT_CLASS_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0024_fix_enrollment_code_slug')
    ]

    operations = [
        migrations.RunPython(create_product_class, remove_product_class),
    ]
