from django.contrib.sites.models import Site
import factory
from oscar.core.loading import get_model

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
