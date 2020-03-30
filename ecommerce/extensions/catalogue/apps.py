from __future__ import absolute_import

from oscar.apps.catalogue import apps


class CatalogueConfig(apps.CatalogueConfig):
    name = 'ecommerce.extensions.catalogue'
