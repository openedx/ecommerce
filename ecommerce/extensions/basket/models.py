from django.db import models
from django.utils.translation import ugettext_lazy as _
from oscar.apps.basket.abstract_models import AbstractBasket
from oscar.core.loading import get_class

OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class Basket(AbstractBasket):
    site = models.ForeignKey('sites.Site', verbose_name=_("Site"), null=True, blank=True, default=None,
                             on_delete=models.SET_NULL)

    @property
    def order_number(self):
        return OrderNumberGenerator().order_number(self)

    def __unicode__(self):
        return _(u"{id} - {status} basket (owner: {owner}, lines: {num_lines})").format(
            id=self.id,
            status=self.status,
            owner=self.owner,
            num_lines=self.num_lines)


# noinspection PyUnresolvedReferences
from oscar.apps.basket.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
