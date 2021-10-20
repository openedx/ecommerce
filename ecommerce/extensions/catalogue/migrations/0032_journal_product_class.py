# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.utils import slugify

JOURNAL_PRODUCT_CLASS_NAME = 'Journal'
JOURNAL_SLUG_NAME = slugify(JOURNAL_PRODUCT_CLASS_NAME)


def create_product_class(apps, schema_editor):
    """ Create a journal product class """
    Category = apps.get_model("catalogue", "Category")
    Product = apps.get_model('catalogue', 'Product')
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    for klass in (Category, Product, ProductClass, ProductAttribute):
        klass.skip_history_when_saving = True

    # Create a new product class for journal
    journal = ProductClass(
        track_stock=False,
        requires_shipping=False,
        name=JOURNAL_PRODUCT_CLASS_NAME,
        slug=JOURNAL_SLUG_NAME
    )
    journal.save()

    # Create product attributes for journal products
    pa1 = ProductAttribute.objects.create(
        product_class=journal,
        name="UUID",
        code="UUID",
        type="text",
        required=True
    )
    pa1.save()

    # Create a category for the journal
    c = Category(
        description="All journals",
        slug="journals",
        image="",
        name="Journals",
        depth=1,
        path='0005',
    )
    c.save()


def remove_product_class(apps, schema_editor):
    """ Reverse function. """
    Category = apps.get_model("catalogue", "Category")
    Product = apps.get_model('catalogue', 'Product')
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    # ProductAttribute is required here for the cascading delete
    for klass in (Category, Product, ProductClass, ProductAttribute):
        klass.skip_history_when_saving = True

    Product.objects.filter(product_class=ProductClass.objects.get(name=JOURNAL_PRODUCT_CLASS_NAME)).delete()
    Category.objects.filter(slug=JOURNAL_SLUG_NAME).delete()
    ProductClass.objects.filter(name=JOURNAL_PRODUCT_CLASS_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0031_course_entitlement_idverifyreq_attr')
    ]

    operations = [
        migrations.RunPython(create_product_class, remove_product_class),
    ]
