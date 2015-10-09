from oscar.apps.basket.abstract_models import AbstractBasket
from oscar.core.loading import get_class


OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class Basket(AbstractBasket):
    @property
    def order_number(self):
        return OrderNumberGenerator().order_number(self)


from oscar.apps.basket.models import *  # noqa pylint: disable=wildcard-import,unused-wildcard-import
