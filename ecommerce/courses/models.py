import logging

from django.db import models
from oscar.core.loading import get_model

logger = logging.getLogger(__name__)
ProductClass = get_model('catalogue', 'ProductClass')


class Course(models.Model):
    id = models.CharField(null=False, max_length=255, primary_key=True, verbose_name='ID')
    name = models.CharField(null=False, max_length=255)

    @classmethod
    def is_mode_verified(cls, mode):
        """ Returns True if the mode is verified, otherwise False. """
        return mode.lower() in ('verified', 'professional', 'credit')

    @classmethod
    def certificate_type_for_mode(cls, mode):
        mode = mode.lower()

        if mode == 'no-id-professional':
            return 'professional'

        return mode

    @property
    def seat_products(self):
        """ Returns a list of course seat Products related to this course. """
        seat_product_class = ProductClass.objects.get(slug='seat')
        products = set()

        for product in self.products.all():
            if product.get_product_class() == seat_product_class:
                if product.is_parent:
                    products.update(product.children.all())
                else:
                    products.add(product)

        return list(products)

    def __unicode__(self):
        return self.id
