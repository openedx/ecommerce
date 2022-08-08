# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME


def create_product_attribute(apps, schema_editor):
    """ Create a product attribute for course entitlement product class"""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    for klass in (ProductAttribute, ProductClass):
        klass.skip_history_when_saving = True

    course_entitlement = ProductClass.objects.get(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)

    # Create product attribute for course entitlement products
    pa1 = ProductAttribute(
        product_class=course_entitlement,
        name="variant_id",
        code="variant_id",
        type="text",
        required=False
    )
    pa1.save()


def remove_product_attribute(apps, schema_editor):
    """ Reverse function. """
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.filter(name='variant_id').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0053_auto_20210922_1857'),
    ]

    operations = [
        migrations.RunPython(create_product_attribute, remove_product_attribute),
    ]
