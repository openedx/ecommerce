# -*- coding: utf-8 -*-


from django.db import migrations
from oscar.core.loading import get_model

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME

ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


def create_idverifyreq_attribute(apps, schema_editor):
    """Create enrollment code 'id_verification_required' attribute."""
    ProductAttribute.skip_history_when_saving = True
    enrollment_code_class = ProductClass.objects.get(name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
    pa = ProductAttribute(
        product_class=enrollment_code_class,
        name='id_verification_required',
        code='id_verification_required',
        type='boolean',
        required=False
    )
    pa.save()


def remove_idverifyreq_attribute(apps, schema_editor):
    """Remove enrollment code 'id_verification_required' attribute."""
    ProductAttribute.skip_history_when_saving = True
    enrollment_code_class = ProductClass.objects.get(name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
    ProductAttribute.objects.get(product_class=enrollment_code_class, name='id_verification_required').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0018_auto_20160530_0134')
    ]
    operations = [
        migrations.RunPython(create_idverifyreq_attribute, remove_idverifyreq_attribute)
    ]
