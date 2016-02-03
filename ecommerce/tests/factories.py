from decimal import Decimal

from django.contrib.sites.models import Site
import factory
from oscar.core.loading import get_model
from oscar.test.factories import ProductFactory

from ecommerce.core.models import SiteConfiguration


class PartnerFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = get_model('partner', 'Partner')
        django_get_or_create = ('name',)

    short_code = factory.SelfAttribute('name')


class SiteFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = Site


class SiteConfigurationFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = SiteConfiguration

    site = factory.SubFactory(SiteFactory)
    partner = factory.SubFactory(PartnerFactory)


class StockRecordFactory(factory.DjangoModelFactory):
    product = factory.SubFactory(ProductFactory)
    partner = factory.SubFactory(PartnerFactory)
    partner_sku = factory.Sequence(lambda n: 'unit%d' % n)
    price_currency = "USD"
    price_excl_tax = Decimal('9.99')
    num_in_stock = 100

    class Meta(object):
        model = get_model('partner', 'StockRecord')
