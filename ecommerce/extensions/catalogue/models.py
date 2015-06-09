# noinspection PyUnresolvedReferences
from django.db import models
from oscar.apps.catalogue.abstract_models import AbstractProduct, AbstractProductAttributeValue
from simple_history.models import HistoricalRecords


class Product(AbstractProduct):
    course = models.ForeignKey('courses.Course', null=True, blank=True, related_name='products')
    changed_by = models.ForeignKey('user.User', null=True, blank=True)
    history = HistoricalRecords()

    @property
    def _history_user(self):  # pragma: no cover
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):  # pragma: no cover
        self.changed_by = value


class ProductAttributeValue(AbstractProductAttributeValue):
    changed_by = models.ForeignKey('user.User', null=True, blank=True)
    history = HistoricalRecords()

    @property
    def _history_user(self):  # pragma: no cover
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):  # pragma: no cover
        self.changed_by = value

# noinspection PyUnresolvedReferences
from oscar.apps.catalogue.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
