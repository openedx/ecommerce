from __future__ import absolute_import

from oscar.apps.dashboard.offers import apps


class OffersDashboardConfig(apps.OffersDashboardConfig):
    name = 'ecommerce.extensions.dashboard.offers'
