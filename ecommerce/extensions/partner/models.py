from django.db import models
from oscar.apps.partner.abstract_models import AbstractStockRecord
from simple_history.models import HistoricalRecords


class StockRecord(AbstractStockRecord):
    changed_by = models.ForeignKey('user.User', null=True, blank=True)
    history = HistoricalRecords()

    @property
    def _history_user(self):  # pragma: no cover
        return self.changed_by

    @_history_user.setter
    def _history_user(self, value):  # pragma: no cover
        self.changed_by = value

# noinspection PyUnresolvedReferences
from oscar.apps.partner.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
