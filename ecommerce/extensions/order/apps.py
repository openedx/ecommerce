from __future__ import absolute_import

from oscar.apps.order import apps


class OrderConfig(apps.OrderConfig):
    name = 'ecommerce.extensions.order'
