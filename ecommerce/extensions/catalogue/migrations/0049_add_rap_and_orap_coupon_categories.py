""" Add no rev 'rap and orap' categories to the list of default coupon categories"""



from django.db import migrations
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

Category = get_model('catalogue', 'Category')

COUPON_CATEGORY_NAME = 'Coupons'

RAP_CATEGORIES = [
    'Partner No Rev - RAP',
    'Partner No Rev - ORAP',
]

def create_rap_categories(apps, schema_editor):
    """Create rap coupon categories."""
    Category.skip_history_when_saving = True
    for category in RAP_CATEGORIES:
        create_from_breadcrumbs('{} > {}'.format(COUPON_CATEGORY_NAME, category))


def remove_rap_categories(apps, schema_editor):
    """Remove rap coupon categories."""
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
