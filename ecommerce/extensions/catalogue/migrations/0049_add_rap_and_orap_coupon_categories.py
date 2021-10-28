""" Add no rev 'rap and orap' categories to the list of default coupon categories"""



from django.db import migrations

from ecommerce.extensions.catalogue.utils import create_subcategories

COUPON_CATEGORY_NAME = 'Coupons'

RAP_CATEGORIES = [
    'Partner No Rev - RAP',
    'Partner No Rev - ORAP',
]

def create_rap_categories(apps, schema_editor):
    """Create rap coupon categories."""
    Category = apps.get_model("catalogue", "Category")

    Category.skip_history_when_saving = True
    create_subcategories(Category, COUPON_CATEGORY_NAME, RAP_CATEGORIES)


def remove_rap_categories(apps, schema_editor):
    """Remove rap coupon categories."""
    Category = apps.get_model("catalogue", "Category")

    Category.skip_history_when_saving = True
    Category.objects.get(name=COUPON_CATEGORY_NAME).get_children().filter(
        name__in=RAP_CATEGORIES
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('catalogue', '0048_auto_20200311_1240'),
    ]

    operations = [
        migrations.RunPython(create_rap_categories, remove_rap_categories)
    ]
