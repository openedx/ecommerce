import json

from django.core.urlresolvers import reverse
from django.test import TestCase
from oscar.core.loading import get_model

from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.mixins import PartnerMixin, UserMixin


Catalog = get_model('catalogue', 'Catalog')
Partner = get_model('partner', 'Partner')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')


class PartnerCatalogViewSetTest(PartnerMixin, CourseCatalogTestMixin, UserMixin, TestCase):

    def setUp(self):
        super(PartnerCatalogViewSetTest, self).setUp()

        # Create and login the user with staff access.
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        # Create partner and add course seat for that partner
        self.edx_partner = self.create_partner('edx')
        self.course = Course.objects.create(id='edX/DemoX/Demo_Course', name='Demo Course')
        self.seat = self.course.create_or_update_seat('honor', False, 0, self.edx_partner)

        # Create stock record and add it to a catalog.
        stock_record = StockRecord.objects.get(partner=self.partner)
        self.catalog = Catalog.objects.create(name='dummy', partner=self.partner)
        self.catalog.stock_records.add(stock_record)

        # URL for getting catalog for partner.
        self.url = reverse(
            'api:v2:partner-catalogs-list',
            kwargs={'parent_lookup_partner_id': self.edx_partner.id},
        )

    def serialize_catalog(self, catalog):
        """Serialize catalog data for expected API response."""
        data = {
            'id': catalog.id,
            'name': catalog.name,
            'partner': catalog.partner.id,
            'stock_records': [catalog.stock_records.count()]
        }
        return data

    def test_get_partner_catalogs(self):
        """Verify the endpoint returns all catalogs associated with a specific partner."""
        response = self.client.get(self.url)
        expected_data = self.serialize_catalog(self.catalog)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(json.loads(response.content)['results'], [expected_data])

    def test_access_catalog_api(self):
        """Verify only staff users can access the endpoint."""
        self.client.logout()
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_no_partner_catalog(self):
        """Verify the endpoint returns an empty result set if the partner has
        no associated catalogs.
        """
        Catalog.objects.filter(name='dummy', partner=self.partner).delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        expected = {
            'count': 0,
            'next': None,
            'previous': None,
            'results': []
        }
        self.assertDictEqual(json.loads(response.content), expected)
