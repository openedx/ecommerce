

from django.urls import reverse
from oscar.core.loading import get_model

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin

Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')


class CatalogMixin(DiscoveryTestMixin):
    """Provide methods for Catalog test cases."""

    def setUp(self):
        super(CatalogMixin, self).setUp()
        # Create the user with staff access.
        self.user = self.create_user(is_staff=True)

        # Create course seat for edx partner
        self.course = CourseFactory(id='edX/DemoX/Demo_Course', name='Demo Course', partner=self.partner)
        self.seat = self.course.create_or_update_seat('honor', False, 0)

        # Create Catalog and stockRecord objects.
        self.catalog = Catalog.objects.create(name='dummy', partner=self.partner)
        self.stock_record = StockRecord.objects.first()

    def serialize_catalog(self, catalog):
        """Serialize catalog data for expected API response."""
        data = {
            'id': catalog.id,
            'partner': catalog.partner.id,
            'name': catalog.name,
            'products': self.get_full_url(reverse('api:v2:catalog-product-list',
                                                  kwargs={'parent_lookup_stockrecords__catalogs': catalog.id}))
        }
        return data
