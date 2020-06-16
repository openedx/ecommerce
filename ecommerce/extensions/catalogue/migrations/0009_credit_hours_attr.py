# -*- coding: utf-8 -*-


from django.db import migrations, models

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME


def create_credit_hours_attribute(apps, schema_editor):

    # Get seat Object
    ProductClass = apps.get_model('catalogue', 'ProductClass')
    seat = ProductClass.objects.get(name=SEAT_PRODUCT_CLASS_NAME)

    # Create our Product Attributes
    ProductAttribute = apps.get_model('catalogue', 'ProductAttribute')
    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.create(
        product_class=seat,
        name='credit_hours',
        code='credit_hours',
        type='integer',
        required=False
    )


def delete_credit_hours_attribute(apps, schema_editor):
    """For backward compatibility"""

    # Delete our Product Attributes
    ProductAttribute = apps.get_model('catalogue', 'ProductAttribute')
    ProductAttribute.skip_history_when_saving = True
    ProductAttribute.objects.filter(code='credit_hours').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogue', '0008_auto_20150709_1254'),
    ]

    operations = [
        migrations.RunPython(create_credit_hours_attribute, delete_credit_hours_attribute),
    ]
