# -*- coding: utf-8 -*-


from django.db import migrations, models
from oscar.core.loading import get_model
from oscar.core.utils import slugify

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME

Category = get_model("catalogue", "Category")
Product = get_model('catalogue', 'Product')
ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def rename_product_attr(apps, schema_editor):
    """ Rename course_entitlement product attr. """
    ProductAttribute.skip_history_when_saving = True
    course_entitlement_class = ProductClass.objects.get(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)
    product_attr = ProductAttribute.objects.get(product_class=course_entitlement_class, name="course_key")

    product_attr.name = 'UUID'
    product_attr.code = 'UUID'
    product_attr.save()


def remove_product_attr(apps, schema_editor):
    """ Remove product attr """
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
