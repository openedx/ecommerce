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


class ProductAttributeValue(AbstractProductAttributeValue):
    history = HistoricalRecords()

# noinspection PyUnresolvedReferences
from oscar.apps.catalogue.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
