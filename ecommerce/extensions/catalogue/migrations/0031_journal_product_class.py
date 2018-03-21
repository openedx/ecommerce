# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from oscar.core.loading import get_model
from oscar.core.utils import slugify

from ecommerce.journal.constants import JOURNAL_PRODUCT_CLASS_NAME

Category = get_model("catalogue", "Category")
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")
JOURNAL_SLUG_NAME = slugify(JOURNAL_PRODUCT_CLASS_NAME)


def create_product_class(apps, schema_editor):
    """ Create a journal product class """

    # Create a new product class for journal
    journal = ProductClass.objects.create(
        track_stock=False,
        requires_shipping=False,
        name=JOURNAL_PRODUCT_CLASS_NAME,
        slug=JOURNAL_SLUG_NAME
    )

    # Create product attributes for journal products
    ProductAttribute.objects.create(
        product_class=journal,
        name="UUID",
        code="UUID",
        type="text",
        required=True
    )

    # Create a category for the journal
    Category.add_root(
        description="All journals",
        slug="journals",
        image="",
        name="Journals"
    )


def remove_product_class(apps, schema_editor):
    """ Reverse function. """
    Product.objects.filter(product_class=ProductClass.objects.get(name=JOURNAL_PRODUCT_CLASS_NAME)).delete()
    Category.objects.filter(slug=JOURNAL_SLUG_NAME).delete()
    ProductClass.objects.filter(name=JOURNAL_PRODUCT_CLASS_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0024_fix_enrollment_code_slug')
    ]

    operations = [
        migrations.RunPython(create_product_class, remove_product_class),
    ]
