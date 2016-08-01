from django.contrib.sites.models import Site
import factory
from factory.fuzzy import FuzzyText
from oscar.core.loading import get_model
from oscar.test.factories import ProductFactory, StockRecordFactory as OscarStockRecordFactory

from ecommerce.core.models import BusinessClient, SiteConfiguration


class BusinessClientFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = BusinessClient

    name = FuzzyText(prefix='test-client-')


class CatalogFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = get_model('catalogue', 'Catalog')

    name = FuzzyText(prefix='test-catalog-')


class PartnerFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = get_model('partner', 'Partner')
        django_get_or_create = ('name',)

    name = FuzzyText(prefix='test-partner-')
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
