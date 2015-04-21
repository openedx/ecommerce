from django.dispatch import receiver
from oscar.core.loading import get_class


post_checkout = get_class('checkout.signals', 'post_checkout')


@receiver(post_checkout, dispatch_uid='fulfillment.post_checkout_callback')
def post_checkout_callback(sender, order=None, **kwargs):  # pylint: disable=unused-argument
    # Note (CCB): This is a minor hack to appease coverage. Since this file is loaded before coverage, the imported
    # module will also be loaded before coverage. Module loaded after coverage are falsely listed as not covered.
    # We do not want the false report, and we do not want to omit the api module from coverage reports. This is the
    # "happy" medium.
    from ecommerce.extensions.fulfillment import api

    # TODO Determine if we need to create ShippingEvents first.
    api.fulfill_order(order, order.lines.all())
