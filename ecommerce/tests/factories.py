from django.contrib.sites.models import Site
import factory
from oscar.core.loading import get_model
from oscar.test.factories import ProductFactory, StockRecordFactory as OscarStockRecordFactory

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

    lms_url_root = factory.LazyAttribute(lambda obj: "http://lms.testserver.fake")
    site = factory.SubFactory(SiteFactory)
    partner = factory.SubFactory(PartnerFactory)


class StockRecordFactory(OscarStockRecordFactory):
    product = factory.SubFactory(ProductFactory)
    price_currency = 'USD'
