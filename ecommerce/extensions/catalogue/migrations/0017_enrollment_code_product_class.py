# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations
from oscar.core.loading import get_model

Category = get_model('catalogue', 'Category')
ProductAttribute = get_model('catalogue', 'ProductAttribute')
ProductClass = get_model('catalogue', 'ProductClass')


def create_enrollment_code_product_class(apps, schema_editor):
    """Create a Enrollment code product class."""

    enrollment_code = ProductClass.objects.create(
        track_stock=False,
        requires_shipping=False,
        name='Enrollment code',
        slug='enrollment_code',
    )

    ProductAttribute.objects.create(
        product_class=enrollment_code,
        name='Course Key',
        code='course_key',
        type='text',
        required=True
    )

    ProductAttribute.objects.create(
        product_class=enrollment_code,
        name='Seat type',
        code='seat_type',
        type='text',
        required=True
    )

    seat_product_class = ProductClass.objects.get(slug='seat')
    ProductAttribute.objects.create(
        product_class=seat_product_class,
        name='Enrollment code',
        code='enrollment_code',
        type='entity',
        required=False
    )


def remove_enrollment_code_product_class(apps, schema_editor):
    """Remove the Enrollment code product class."""
    ProductAttribute.objects.get(code='enrollment_code').delete()
    ProductClass.objects.filter(slug='enrollment_code').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0001_initial'),
        ('catalogue', '0016_coupon_note_attribute')
    ]
    operations = [
        migrations.RunPython(create_enrollment_code_product_class, remove_enrollment_code_product_class)
    ]
