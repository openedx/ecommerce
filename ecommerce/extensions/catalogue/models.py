# noinspection PyUnresolvedReferences
from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.catalogue.abstract_models import AbstractProduct, AbstractProductAttributeValue
from simple_history.models import HistoricalRecords

from ecommerce.core.constants import (
    COUPON_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_PRODUCT_CLASS_NAME, SEAT_PRODUCT_CLASS_NAME
)


class Product(AbstractProduct):
    course = models.ForeignKey(
        'courses.Course', null=True, blank=True, related_name='products', on_delete=models.CASCADE
    )
    expires = models.DateTimeField(null=True, blank=True,
                                   help_text=_('Last date/time on which this product can be purchased.'))
    history = HistoricalRecords()

    @property
    def is_seat_product(self):
        return self.get_product_class().name == SEAT_PRODUCT_CLASS_NAME

    @property
    def is_enrollment_code_product(self):
        return self.get_product_class().name == ENROLLMENT_CODE_PRODUCT_CLASS_NAME

    @property
    def is_coupon_product(self):
        return self.get_product_class().name == COUPON_PRODUCT_CLASS_NAME


class ProductAttributeValue(AbstractProductAttributeValue):
    history = HistoricalRecords()


class Catalog(models.Model):
    name = models.CharField(max_length=255)
    partner = models.ForeignKey('partner.Partner', related_name='catalogs', on_delete=models.CASCADE)
    stock_records = models.ManyToManyField('partner.StockRecord', blank=True, related_name='catalogs')

    def __unicode__(self):
        return u'{id}: {partner_code}-{catalog_name}'.format(
            id=self.id,
            partner_code=self.partner.short_code,
            catalog_name=self.name
        )


# noinspection PyUnresolvedReferences
from oscar.apps.catalogue.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,ungrouped-imports,wrong-import-order
