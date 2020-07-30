# -*- coding: utf-8 -*-


from django.db import migrations, models
from oscar.core.utils import slugify

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME


def rename_product_attr(apps, schema_editor):
    """ Rename course_entitlement product attr. """
    Category = apps.get_model("catalogue", "Category")
    Product = apps.get_model('catalogue', 'Product')
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    ProductAttribute.skip_history_when_saving = True
    course_entitlement_class = ProductClass.objects.get(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)
    product_attr = ProductAttribute.objects.get(product_class=course_entitlement_class, name="course_key")

    product_attr.name = 'UUID'
    product_attr.code = 'UUID'
    product_attr.save()


def remove_product_attr(apps, schema_editor):
    """ Remove product attr """
    Category = apps.get_model("catalogue", "Category")
    Product = apps.get_model('catalogue', 'Product')
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    ProductAttribute.skip_history_when_saving = True

    course_entitlement_class = ProductClass.objects.get(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)
    product_attr = ProductAttribute.objects.get(product_class=course_entitlement_class, name="UUID")

    product_attr.name = 'course_key'
    product_attr.code = 'course_key'
    product_attr.save()



class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0025_course_entitlement')
    ]

    operations = [
        migrations.RunPython(rename_product_attr, remove_product_attr),
    ]
