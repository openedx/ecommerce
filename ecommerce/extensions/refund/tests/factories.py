

from decimal import Decimal

import factory
from django.conf import settings
from oscar.core.loading import get_model

from ecommerce.extensions.refund.status import REFUND, REFUND_LINE
from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.factories import SiteConfigurationFactory, UserFactory

Category = get_model("catalogue", "Category")
Partner = get_model('partner', 'Partner')
Product = get_model("catalogue", "Product")
ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")


class RefundFactory(factory.DjangoModelFactory):
    status = getattr(settings, 'OSCAR_INITIAL_REFUND_STATUS', REFUND.OPEN)
    user = factory.SubFactory(UserFactory)
    total_credit_excl_tax = Decimal(1.00)

    @factory.lazy_attribute
    def order(self):
        site = SiteConfigurationFactory().site
        return create_order(site=site, user=self.user)

    @factory.post_generation
    def create_lines(self, create, extracted, **kwargs):  # pylint: disable=unused-argument
        if not create:
            return

        for line in self.order.lines.all():
            RefundLineFactory.create(refund=self, order_line=line)

        self.total_credit_excl_tax = sum([line.line_credit_excl_tax for line in self.lines.all()])
        self.save()

    class Meta:
        model = get_model('refund', 'Refund')


class RefundLineFactory(factory.DjangoModelFactory):
    status = getattr(settings, 'OSCAR_INITIAL_REFUND_LINE_STATUS', REFUND_LINE.OPEN)
    refund = factory.SubFactory(RefundFactory)
    line_credit_excl_tax = Decimal(1.00)

    @factory.lazy_attribute
    def order_line(self):
        order = create_order()
        return order.lines.first()

    class Meta:
        model = get_model('refund', 'RefundLine')
