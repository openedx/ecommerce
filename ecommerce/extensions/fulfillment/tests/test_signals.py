from django.test import TestCase, override_settings
from oscar.core.loading import get_class

from ecommerce.extensions.fulfillment.tests.mixins import FulfillmentTestMixin


post_checkout = get_class('checkout.signals', 'post_checkout')


class SignalTests(FulfillmentTestMixin, TestCase):
    @override_settings(FULFILLMENT_MODULES=['ecommerce.extensions.fulfillment.tests.modules.FakeFulfillmentModule', ])
    def test_post_checkout_callback(self):
        """
        When the post_checkout signal is emitted, the receiver should attempt to fulfill the newly-placed order.
        """
        self.assertEqual(len(post_checkout.receivers), 1, 'No receiver connected to to post_checkout signal!')
        order = self.generate_open_order()
        post_checkout.send(sender=self.__class__, order=order)
        self.assert_order_fulfilled(order)
