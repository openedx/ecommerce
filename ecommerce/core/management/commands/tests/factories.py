from __future__ import absolute_import

import factory
from factory.fuzzy import FuzzyInteger
from oscar.core.loading import get_model


class PaymentEventFactory(factory.DjangoModelFactory):
    id = FuzzyInteger(1000, 9999)

    class Meta(object):
        model = get_model('order', 'PaymentEvent')


class SuperUserFactory(factory.DjangoModelFactory):
    id = FuzzyInteger(1000, 9999)
    is_superuser = True

    class Meta(object):
        model = get_model('core', 'User')
