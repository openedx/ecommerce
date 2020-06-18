

from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.partner.abstract_models import AbstractPartner, AbstractStockRecord
from simple_history.models import HistoricalRecords


class StockRecord(AbstractStockRecord):
    history = HistoricalRecords()


class Partner(AbstractPartner):
    # short_code is the unique identifier for the 'Partner'
    short_code = models.CharField(max_length=8, unique=True, null=False, blank=False)
    enable_sailthru = models.BooleanField(default=True, verbose_name=_('Enable Sailthru Reporting'),
                                          help_text='DEPRECATED: Use SiteConfiguration!')
    default_site = models.OneToOneField('sites.Site', null=True, blank=True, on_delete=models.PROTECT)

    history = HistoricalRecords(excluded_fields=['code'])

    class Meta:
        # Model name that will appear in the admin panel
        verbose_name = _('Partner')
        verbose_name_plural = _('Partners')


# noinspection PyUnresolvedReferences
from oscar.apps.partner.models import *  # noqa isort:skip pylint: disable=wildcard-import,unused-wildcard-import,wrong-import-position,ungrouped-imports
