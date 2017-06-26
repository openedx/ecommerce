from oscar.core.loading import get_class, get_model
from oscar.test import factories

from ecommerce.tests.mixins import SiteMixin

Default = get_class('partner.strategy', 'Default')
Basket = get_model('basket', 'Basket')


class BasketMixin(SiteMixin):
    def create_basket(self, owner, site, status=Basket.OPEN, empty=False):
        owner = owner or factories.UserFactory()
        site = site or self.site
        basket = Basket.objects.create(owner=owner, site=site, status=status)
        basket.strategy = Default()
        if not empty:
            product = factories.create_product()
            factories.create_stockrecord(product, num_in_stock=2)
            basket.add_product(product)
        return basket
