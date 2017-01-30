# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from oscar.core.loading import get_model

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME

ProductAttribute = get_model('catalogue', 'ProductAttribute')
ProductClass = get_model('catalogue', 'ProductClass')


def create_enrollment_code_active_attribute(apps, schema_editor):
    """Create a new product attribute 'is_active' for Enrollment code products."""
    ec_class = ProductClass.objects.get(name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
    ProductAttribute.objects.create(
        product_class=ec_class,
        name='Is active',
        code='is_active',
        type='boolean',
        required=True
    )


def remove_enrollment_code_active_attribute(apps, schema_editor):
    """Remove the 'is_active' product attribute."""
    ProductAttribute.objects.get(code='is_active').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0020_auto_20161025_1446')
    ]
    operations = [
        migrations.RunPython(create_enrollment_code_active_attribute, remove_enrollment_code_active_attribute)
    ]
