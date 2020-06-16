# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.loading import get_model
from oscar.core.utils import slugify

from ecommerce.core.constants import DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME

Category = get_model("catalogue", "Category")
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def create_product_class(apps, schema_editor):  # pylint: disable=unused-argument
    """ Create a donation product class for donations from checkout tests """

    ProductClass.skip_history_when_saving = True
    Category.skip_history_when_saving = True

    # Create a new product class for donations for the donations from checkout tests
    donation, __ = ProductClass.objects.get_or_create(
        track_stock=False,
        requires_shipping=False,
        name=DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME,
        slug=slugify(DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME)
    )

    Category.add_root(
        description="All donations",
        slug="donations",
        image="",
        name="Donations"
    )


def remove_product_class(apps, schema_editor):  # pylint: disable=unused-argument
    """ Reverse function. """
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
