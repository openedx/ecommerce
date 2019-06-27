from __future__ import absolute_import

from oscar.apps.order import config


class OrderConfig(config.OrderConfig):
    name = 'ecommerce.extensions.order'
