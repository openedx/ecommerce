

from oscar.apps.dashboard.orders import apps


class OrdersDashboardConfig(apps.OrdersDashboardConfig):
    name = 'ecommerce.extensions.dashboard.orders'
