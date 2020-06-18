

from django.urls import reverse
from oscar.core.loading import get_model

from ecommerce.tests.factories import PartnerFactory
from ecommerce.tests.testcases import TestCase

Partner = get_model('partner', 'Partner')


class PartnerViewTest(TestCase):
    def setUp(self):
        super(PartnerViewTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.dummy_partner = PartnerFactory(name='dummy')

    def serialize_partner(self, partner):
        """Serialize the the data for the partner provided and return the
        expected partner data from API endpoint.
        """
        product_path = reverse('api:v2:partner-product-list',
                               kwargs={'parent_lookup_stockrecords__partner_id': partner.id}, )
        catalog_path = reverse('api:v2:partner-catalogs-list', kwargs={'parent_lookup_partner_id': partner.id}, )
        data = {
            'id': partner.id,
            'name': partner.name,
            'short_code': partner.short_code,
            'catalogs': self.get_full_url(catalog_path),
            'products': self.get_full_url(product_path)
        }
        return data

    def test_get_partner_list(self):
        """Verify the endpoint returns a list of all partners."""
        url = reverse('api:v2:partner-list')
        edx_partner_data = self.serialize_partner(self.partner)
        dummy_partner_data = self.serialize_partner(self.dummy_partner)
        expected_data = list()
        expected_data.append(edx_partner_data)
        expected_data.append(dummy_partner_data)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 2)
        self.assertListEqual(response.json()['results'], expected_data)

    def test_get_partner_detail(self):
        """Verify the endpoint returns the details for a specific partner."""
        url = reverse('api:v2:partner-detail', kwargs={'pk': self.partner.id})
        response = self.client.get(url)
        expected_data = self.serialize_partner(self.partner)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.json(), expected_data)

    def test_access_partner_api(self):
        """Verify the API endpoint requires staff permissions."""
        self.client.logout()
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)
        url = reverse('api:v2:partner-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
