import factory
from factory.fuzzy import FuzzyInteger
from oscar.core.loading import get_model


class PaymentEventFactory(factory.DjangoModelFactory):

    id = FuzzyInteger(1000, 9999)

    class Meta(object):
        model = get_model('order', 'PaymentEvent')
