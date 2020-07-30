# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.loading import get_model
from oscar.core.utils import slugify

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME

Category = get_model('catalogue', 'Category')
ProductAttribute = get_model('catalogue', 'ProductAttribute')
ProductClass = get_model('catalogue', 'ProductClass')


def create_enrollment_code_product_class(apps, schema_editor):
    """Create an Enrollment code product class and switch to turn automatic creation on."""
    for klass in (Category, ProductAttribute, ProductClass):
        klass.skip_history_when_saving = True

    enrollment_code = ProductClass(
        track_stock=False,
        requires_shipping=False,
        name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
        slug=slugify(ENROLLMENT_CODE_PRODUCT_CLASS_NAME),
    )
    enrollment_code.save()

    pa1 = ProductAttribute(
        product_class=enrollment_code,
        name='Course Key',
        code='course_key',
        type='text',
        required=True
    )
    pa1.save()

    pa2 = ProductAttribute(
        product_class=enrollment_code,
        name='Seat Type',
        code='seat_type',
        type='text',
        required=True
    )
    pa2.save()


def remove_enrollment_code_product_class(apps, schema_editor):
    """Remove the Enrollment code product class and the waffle switch."""
    ProductClass.skip_history_when_saving = True
    ProductClass.objects.filter(name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0016_coupon_note_attribute')
    ]
    operations = [
        migrations.RunPython(create_enrollment_code_product_class, remove_enrollment_code_product_class)
    ]
