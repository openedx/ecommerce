# Combined the effect of 25,26,28,31,32,41 migrations to adjust data migrations with latest version
# of django oscar. Will be reversed after successful upgrade.

from django.db import migrations
from oscar.core.loading import get_model
from oscar.core.utils import slugify

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME, \
    DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME


Category = get_model("catalogue", "Category")
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def create_product_class(apps, schema_editor):
    for klass in (Category, ProductAttribute, ProductClass):
        klass.skip_history_when_saving = True
    # Create a new product class for course entitlement
    course_entitlement = ProductClass(
        track_stock=False,
        requires_shipping=False,
        name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME,
        slug=slugify(COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)
    )
    course_entitlement.save()

    # Create product attributes for course entitlement products
    pa1 = ProductAttribute(
        product_class=course_entitlement,
        name="UUID",
        code="UUID",
        type="text",
        required=True
    )
    pa1.save()

    pa2 = ProductAttribute(
        product_class=course_entitlement,
        name="certificate_type",
        code="certificate_type",
        type="text",
        required=False
    )
    pa2.save()

    pa3 = ProductAttribute(
        product_class=course_entitlement,
        name='id_verification_required',
        code='id_verification_required',
        type='boolean',
        required=False
    )
    pa3.save()

    # Create a category for course entitlements
    Category.add_root(
        description="All course entitlements",
        slug="course_entitlements",
        image="",
        name="Course Entitlements"
    )

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


def remove_product_class(apps, schema_editor):
    """ Reverse function. """

    # ProductAttribute is needed for cascading delete
    for klass in (Product, Category, ProductAttribute, ProductClass):
        klass.skip_history_when_saving = True

    Product.objects.filter(product_class=ProductClass.objects.get(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)).delete()
    Category.objects.filter(slug='course_entitlements').delete()
    ProductClass.objects.filter(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME).delete()

    donation_class = ProductClass.objects.get(name=DONATIONS_FROM_CHECKOUT_TESTS_PRODUCT_TYPE_NAME)
    Product.objects.filter(product_class=donation_class).delete()
    Category.objects.filter(slug='donations').delete()
    donation_class.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0051_auto_20200723_1602')
    ]

    operations = [
        migrations.RunPython(create_product_class, remove_product_class),
    ]