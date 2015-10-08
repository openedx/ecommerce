from django.db import models
from oscar.apps.basket.abstract_models import AbstractBasket
from oscar.core.loading import get_class


OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class Basket(AbstractBasket):
    partner = models.ForeignKey('partner.Partner', null=True, blank=True, related_name='baskets')

    @property
    def order_number(self):
        return OrderNumberGenerator().order_number(self)


from oscar.apps.basket.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
