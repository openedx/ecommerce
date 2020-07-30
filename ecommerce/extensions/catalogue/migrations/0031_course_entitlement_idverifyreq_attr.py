# -*- coding: utf-8 -*-


from django.db import migrations

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME


def create_idverifyreq_attribute(apps, schema_editor):
    """Create entitlement code 'id_verification_required' attribute."""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    ProductAttribute.skip_history_when_saving = True

    entitlement_code_class = ProductClass.objects.get(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)
    pa = ProductAttribute(
        product_class=entitlement_code_class,
        name='id_verification_required',
        code='id_verification_required',
        type='boolean',
        required=False
    )
    pa.save()


def remove_idverifyreq_attribute(apps, schema_editor):
    """Remove enrollment code 'id_verification_required' attribute."""
    ProductAttribute = apps.get_model("catalogue", "ProductAttribute")
    ProductClass = apps.get_model("catalogue", "ProductClass")

    enrollment_code_class = ProductClass.objects.get(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)

    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.get(
        product_class=enrollment_code_class,
        name='id_verification_required'
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0025_course_entitlement'),
        ('catalogue', '0030_auto_20180124_1131')
    ]
    operations = [
        migrations.RunPython(create_idverifyreq_attribute, remove_idverifyreq_attribute)
    ]
