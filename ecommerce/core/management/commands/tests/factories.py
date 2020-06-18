

import factory
from factory.fuzzy import FuzzyInteger
from oscar.core.loading import get_model


class PaymentEventFactory(factory.DjangoModelFactory):
    id = FuzzyInteger(1000, 9999)

    class Meta:
        model = get_model('order', 'PaymentEvent')


class SuperUserFactory(factory.DjangoModelFactory):
    id = FuzzyInteger(1000, 9999)
    is_superuser = True
    lms_user_id = 56765

    class Meta:
        model = get_model('core', 'User')
