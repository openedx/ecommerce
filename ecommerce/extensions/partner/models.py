from oscar.apps.partner.abstract_models import AbstractStockRecord
from simple_history.models import HistoricalRecords


class StockRecord(AbstractStockRecord):
    history = HistoricalRecords()

# noinspection PyUnresolvedReferences
from oscar.apps.partner.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
