from __future__ import absolute_import

from oscar.apps.checkout import config


class CheckoutConfig(config.CheckoutConfig):
    name = 'ecommerce.extensions.checkout'
