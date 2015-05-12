from decimal import Decimal
from django.conf import settings

import factory
from oscar.core.loading import get_model
from oscar.test import factories
from oscar.test.newfactories import UserFactory

from ecommerce.extensions.refund.status import REFUND, REFUND_LINE


class RefundFactory(factory.DjangoModelFactory):
    status = getattr(settings, 'OSCAR_INITIAL_REFUND_STATUS', REFUND.OPEN)
    user = factory.SubFactory(UserFactory)
    total_credit_excl_tax = Decimal(1.00)

    @factory.lazy_attribute
    def order(self):
        return factories.create_order(user=self.user)

    class Meta(object):
        model = get_model('refund', 'Refund')


class RefundLineFactory(factory.DjangoModelFactory):
    status = getattr(settings, 'OSCAR_INITIAL_REFUND_LINE_STATUS', REFUND_LINE.OPEN)
    refund = factory.SubFactory(RefundFactory)
    line_credit_excl_tax = Decimal(1.00)

    @factory.lazy_attribute
    def order_line(self):
        order = factories.create_order()
        return order.lines.first()

    class Meta(object):
        model = get_model('refund', 'RefundLine')
