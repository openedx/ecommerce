from __future__ import absolute_import

from oscar.apps.dashboard.orders import config


class OrdersDashboardConfig(config.OrdersDashboardConfig):
    name = 'ecommerce.extensions.dashboard.orders'
