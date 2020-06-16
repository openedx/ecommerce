

import factory
from django.contrib.sites.models import Site
from factory.fuzzy import FuzzyText  # pylint: disable=ungrouped-imports
from faker import Faker
from oscar.core.loading import get_model
from oscar.test.factories import ProductFactory
from oscar.test.factories import StockRecordFactory as OscarStockRecordFactory

from ecommerce.core.models import SiteConfiguration


class PartnerFactory(factory.DjangoModelFactory):
    class Meta:
        model = get_model('partner', 'Partner')
        django_get_or_create = ('name',)

    name = FuzzyText(prefix='test-partner-')
    short_code = FuzzyText(length=8)


class SiteFactory(factory.DjangoModelFactory):
    class Meta:
        model = Site

    domain = FuzzyText(suffix='.fake')
    name = FuzzyText()


class SiteConfigurationFactory(factory.DjangoModelFactory):
    class Meta:
        model = SiteConfiguration

    lms_url_root = factory.LazyAttribute(lambda obj: "http://lms.testserver.fake")
    site = factory.SubFactory(SiteFactory)
    partner = factory.SubFactory(PartnerFactory)
    segment_key = 'fake_key'
    send_refund_notifications = False
    enable_sdn_check = False
    enable_embargo_check = False
    enable_partial_program = False
    discovery_api_url = 'http://{}.fake/'.format(Faker().domain_name())


class StockRecordFactory(OscarStockRecordFactory):
    product = factory.SubFactory(ProductFactory)
    price_currency = 'USD'


class UserFactory(factory.DjangoModelFactory):
    class Meta:
        model = get_model('core', 'User')

    username = factory.Sequence(lambda n: 'ecommerce_test_user %d' % n)
    email = factory.Sequence(lambda n: 'ecommerce_test_%s@example.com' % n)
    first_name = 'Ecommerce'
    last_name = 'User'
    password = factory.PostGenerationMethodCall('set_password', 'somethingSecure')
    is_active = True
    is_superuser = False
    is_staff = False
    lms_user_id = 98789
