

from django.test import override_settings
from oscar.core.loading import get_class

from ecommerce.extensions.fulfillment.tests.mixins import FulfillmentTestMixin
from ecommerce.tests.testcases import TestCase

post_checkout = get_class('checkout.signals', 'post_checkout')


class SignalTests(FulfillmentTestMixin, TestCase):
    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule', ])
    def test_post_checkout_callback(self):
        """
        When the post_checkout signal is emitted, the receiver should attempt to fulfill the newly-placed order.
        """
        self.assertIn(
            'fulfillment.post_checkout_callback',
            [receiver[0][0] for receiver in post_checkout.receivers],
            'Receiver not connected to post_checkout signal!',
        )
        order = self.generate_open_order()
        post_checkout.send(sender=self.__class__, order=order)
        self.assert_order_fulfilled(order)
