from __future__ import unicode_literals
import logging

from oscar.core.loading import get_model
from oscar.test import factories

logger = logging.getLogger(__name__)

Category = get_model('catalogue', 'Category')
Partner = get_model('partner', 'Partner')
ProductClass = get_model('catalogue', 'ProductClass')


class CourseCatalogTestMixin(object):
    """
    Mixin for all tests involving the course catalog or course seats.

    The setup method guarantees the requisite product class, partner, and category will be in place. This is especially
    useful when running tests without database migrations (which normally create these objects).
    """
    def setUp(self):
        super(CourseCatalogTestMixin, self).setUp()

        # Force the creation of a seat ProductClass
        self.seat_product_class  # pylint: disable=pointless-statement
        self.partner, _created = Partner.objects.get_or_create(code='edx')
        self.category, _created = Category.objects.get_or_create(name='Seats', defaults={'depth': 1})

    @property
    def seat_product_class(self):
        defaults = {'requires_shipping': False, 'track_stock': False, 'name': 'Seat'}
        pc, created = ProductClass.objects.get_or_create(slug='seat', defaults=defaults)

        if created:
            attributes = (
                ('certificate_type', 'text'),
                ('course_key', 'text'),
                ('credit_provider', 'text'),
                ('id_verification_required', 'boolean'),
                ('credit_hours', 'integer'),
            )

            for code, attr_type in attributes:
                factories.ProductAttributeFactory(code=code, name=code, product_class=pc, type=attr_type)

        return pc
