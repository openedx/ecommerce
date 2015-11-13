# noinspection PyUnresolvedReferences
from django.db import models
from oscar.apps.offer.abstract_models import AbstractRange


class Range(AbstractRange):
    catalog = models.ForeignKey('catalogue.Catalog', blank=True, null=True, related_name='ranges')

    def contains_product(self, product):
        if self.catalog:
            return product.id in self.catalog.stock_records.values_list('product', flat=True)
        return super(Range, self).contains_product(product)

    def all_products(self):
        if self.catalog:
            products = [record.product for record in self.catalog.stock_records.all()]
            return products
        return super(Range, self).all_products()

from oscar.apps.offer.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
