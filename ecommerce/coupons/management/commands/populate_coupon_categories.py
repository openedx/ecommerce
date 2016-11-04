import logging

from django.core.management import BaseCommand
from oscar.core.loading import get_model

Category = get_model('catalogue', 'Category')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """ Populate the category field for coupons that do not have a category. """
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)

    def handle(self, *args, **options):
        support_other_cat = Category.objects.get(name='Support-Other')
        for coupon in Product.objects.filter(product_class__name='Coupon'):
            try:
                ProductCategory.objects.get(product=coupon)
            except ProductCategory.DoesNotExist:
                ProductCategory.objects.create(
                    product=coupon,
                    category=support_other_cat
                )
                logger.info('Added category for coupon [%s]', coupon.id)
