from django.contrib.sites.models import Site
import factory
from factory.fuzzy import FuzzyText
from oscar.core.loading import get_model, get_class
from oscar.test import factories

from ecommerce.core.models import SiteConfiguration

Basket = get_model('basket', 'Basket')
Selector = get_class('partner.strategy', 'Selector')


class PartnerFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = get_model('partner', 'Partner')
        django_get_or_create = ('name',)

    name = FuzzyText()
    short_code = factory.SelfAttribute('name')


class SiteFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = Site


class SiteConfigurationFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = SiteConfiguration

    site = factory.SubFactory(SiteFactory)
    partner = factory.SubFactory(PartnerFactory)


def create_basket(user, site, status=Basket.OPEN):
    """ Create a new Basket for the user and site. """
    basket = factories.create_basket()
    basket.owner = user
    basket.site = site
    basket.status = status

    basket.strategy = Selector().strategy(user=user, site=site)

    basket.save()
    return basket
