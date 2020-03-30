from __future__ import absolute_import

from oscar.apps.partner import apps


class PartnerConfig(apps.PartnerConfig):
    name = 'ecommerce.extensions.partner'
