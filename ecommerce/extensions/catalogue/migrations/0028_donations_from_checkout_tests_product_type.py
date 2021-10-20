# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.utils import slugify

from ecommerce.core.constants import DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME


def create_product_class(apps, schema_editor):  # pylint: disable=unused-argument
    """ Create a donation product class for donations from checkout tests """
    Category = apps.get_model("catalogue", "Category")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    ProductClass.skip_history_when_saving = True
    Category.skip_history_when_saving = True

    # Create a new product class for donations for the donations from checkout tests
    donation, __ = ProductClass.objects.get_or_create(
        track_stock=False,
        requires_shipping=False,
        name=DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME,
        slug=slugify(DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME)
    )

    # Create a category for donations.
    c = Category(
        description="All donations",
        slug="donations",
        image="",
        name="Donations",
        depth=1,
        path='0004',
    )
    c.save()


def remove_product_class(apps, schema_editor):  # pylint: disable=unused-argument
    """ Reverse function. """
    Category = apps.get_model("catalogue", "Category")
    Product = apps.get_model('catalogue', 'Product')
    ProductClass = apps.get_model("catalogue", "ProductClass")

    ProductClass.skip_history_when_saving = True
    Product.skip_history_when_saving = True
    Category.skip_history_when_saving = True

    donation_class = ProductClass.objects.get(name=DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME)
    Product.objects.filter(product_class=donation_class).delete()
    Category.objects.filter(slug='donations').delete()
    donation_class.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0027_catalogue_entitlement_option')
    ]

    operations = [
        migrations.RunPython(create_product_class, remove_product_class),
    ]
