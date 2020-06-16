

import factory
from oscar.test.factories import BasketFactory

from ecommerce.referrals.models import Referral
from ecommerce.tests.factories import SiteFactory


class ReferralFactory(factory.DjangoModelFactory):
    class Meta:
        model = Referral

    basket = factory.SubFactory(BasketFactory)
    site = factory.SubFactory(SiteFactory)
