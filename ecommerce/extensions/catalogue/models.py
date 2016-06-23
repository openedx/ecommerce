# noinspection PyUnresolvedReferences
from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.catalogue.abstract_models import AbstractProduct, AbstractProductAttributeValue
from simple_history.models import HistoricalRecords


class Product(AbstractProduct):
    course = models.ForeignKey('courses.Course', null=True, blank=True, related_name='products')
    expires = models.DateTimeField(null=True, blank=True,
                                   help_text=_('Last date/time on which this product can be purchased.'))
    history = HistoricalRecords()

    class Meta(AbstractProduct.Meta):
        get_latest_by = 'date_created'


class ProductAttributeValue(AbstractProductAttributeValue):
    history = HistoricalRecords()


class Catalog(models.Model):
    name = models.CharField(max_length=255)
    partner = models.ForeignKey('partner.Partner', related_name='catalogs')
    stock_records = models.ManyToManyField('partner.StockRecord', blank=True, related_name='catalogs')

    def __unicode__(self):
        return u'{id}: {partner_code}-{catalog_name}'.format(
            id=self.id,
            partner_code=self.partner.short_code,
            catalog_name=self.name
        )


# noinspection PyUnresolvedReferences
from oscar.apps.catalogue.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,ungrouped-imports
