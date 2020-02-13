from __future__ import absolute_import

from oscar.apps.dashboard.users import apps


class UsersDashboardConfig(apps.UsersDashboardConfig):
    name = 'ecommerce.extensions.dashboard.users'
