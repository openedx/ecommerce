

import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel

logger = logging.getLogger(__name__)


class Referral(TimeStampedModel):
    ATTRIBUTION_ATTRIBUTES = (
        'affiliate_id',
        'utm_source',
        'utm_medium',
        'utm_campaign',
        'utm_term',
        'utm_content',
        'utm_created_at',
    )

    site = models.ForeignKey('sites.Site', null=True, blank=False, on_delete=models.CASCADE)
    basket = models.OneToOneField('basket.Basket', null=True, blank=True, on_delete=models.SET_NULL)
    order = models.OneToOneField('order.Order', null=True, blank=True, on_delete=models.SET_NULL)
    affiliate_id = models.CharField(_('Affiliate ID'), blank=True, default="", max_length=255)
    utm_source = models.CharField(_('UTM Source'), blank=True, default="", max_length=255)
    utm_medium = models.CharField(_('UTM Medium'), blank=True, default="", max_length=255)
    utm_campaign = models.CharField(_('UTM Campaign'), blank=True, default="", max_length=255)
    utm_term = models.CharField(_('UTM Term'), blank=True, default="", max_length=255)
    utm_content = models.CharField(_('UTM Content'), blank=True, default="", max_length=255)
    utm_created_at = models.DateTimeField(_('UTM Created At'), null=True, blank=True, default=None)
