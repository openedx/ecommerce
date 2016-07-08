import factory
from factory.fuzzy import FuzzyText
from oscar.test import factories

from ecommerce.referrals.models import Referral


class ReferralFactory(factory.DjangoModelFactory):
    affiliate_id = FuzzyText(prefix='test-affiliate-')
    order = factory.SubFactory(factories.OrderFactory)

    class Meta(object):
        model = Referral
