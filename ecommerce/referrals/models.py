from __future__ import unicode_literals
import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel

logger = logging.getLogger(__name__)


class Referral(TimeStampedModel):
    affiliate_id = models.CharField(_('Affiliate ID'), null=False, blank=False, default=None, max_length=255)
    basket = models.OneToOneField('basket.Basket', null=True, blank=True)
    order = models.OneToOneField('order.Order', null=True, blank=True)
