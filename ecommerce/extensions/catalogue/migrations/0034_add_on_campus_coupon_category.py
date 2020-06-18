""" Add 'On-Campus Learners' to the list of default coupon categories"""



from django.db import migrations
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

Category = get_model('catalogue', 'Category')

COUPON_CATEGORY_NAME = 'Coupons'

ON_CAMPUS_CATEGORY = 'On-Campus Learners'


def create_on_campus_category(apps, schema_editor):
    """ Create on-campus coupon category """
    Category.skip_history_when_saving = True
    create_from_breadcrumbs('{} > {}'.format(COUPON_CATEGORY_NAME, ON_CAMPUS_CATEGORY))


def remove_on_campus_category(apps, schema_editor):
    """ Remove on-campus coupon category """
    Category.skip_history_when_saving = True
    Category.objects.get(
        name=COUPON_CATEGORY_NAME
    ).get_children().filter(
        name=ON_CAMPUS_CATEGORY
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('catalogue', '0033_add_coupon_categories')
    ]

    operations = [
        migrations.RunPython(create_on_campus_category, remove_on_campus_category)
    ]
