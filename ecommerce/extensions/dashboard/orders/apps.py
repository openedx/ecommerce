from __future__ import absolute_import

from oscar.apps.dashboard.orders import apps


class OrdersDashboardConfig(apps.OrdersDashboardConfig):
    name = 'ecommerce.extensions.dashboard.orders'
