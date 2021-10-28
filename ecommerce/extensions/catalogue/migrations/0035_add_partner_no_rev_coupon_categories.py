""" Add 'Partner No Rev' categories to the list of default coupon categories"""



from django.db import migrations

from ecommerce.extensions.catalogue.utils import create_subcategories

COUPON_CATEGORY_NAME = 'Coupons'

DEFAULT_CATEGORIES = [
    'Partner No Rev - Prepay',
    'Partner No Rev - Upon Redemption',
]


def create_default_categories(apps, schema_editor):
    """Create default coupon categories."""
    Category = apps.get_model("catalogue", "Category")

    Category.skip_history_when_saving = True
    create_subcategories(Category, COUPON_CATEGORY_NAME, DEFAULT_CATEGORIES)


def remove_default_categories(apps, schema_editor):
    """Remove default coupon categories."""
    Category = apps.get_model("catalogue", "Category")
    Category.skip_history_when_saving = True
    Category.objects.get(name=COUPON_CATEGORY_NAME).get_children().filter(
        name__in=DEFAULT_CATEGORIES
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('catalogue', '0034_add_on_campus_coupon_category'),
    ]

    operations = [
        migrations.RunPython(create_default_categories, remove_default_categories)
    ]
