import logging

from django.core.management import BaseCommand
from oscar.core.loading import get_model

logger = logging.getLogger(__name__)
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')

WRONG_SLUG = 'enrollment-code'
RIGHT_SLUG = 'enrollment_code'


class Command(BaseCommand):
    """Remove product class with wrong slug."""
    def handle(self, *args, **kwargs):  # pylint: disable=unused-argument
        faulty_product_class = ProductClass.objects.filter(slug=WRONG_SLUG).first()
        right_product_class = ProductClass.objects.filter(slug=RIGHT_SLUG).first()

        if faulty_product_class and right_product_class:
            logger.info('Faulty and right product class found.')
            enrollment_codes = Product.objects.filter(product_class=faulty_product_class)
            logger.info('Found %d enrollment codes with faulty product class.', enrollment_codes.count())

            enrollment_codes.update(product_class=right_product_class)
            faulty_product_class.delete()
            remaining = Product.objects.filter(product_class=faulty_product_class).count()
            logger.info(
                'Faulty product class deleted. %d enrollment codes with faulty product class remain.',
                remaining
            )
        elif faulty_product_class:
            logger.info('Faulty product class found.')
            faulty_product_class.slug = RIGHT_SLUG
            faulty_product_class.save()
        else:
            logger.info('Faulty product class not found.')
