""" Tests for client API endpoint. """
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.urlresolvers import reverse

from ecommerce.core.models import BusinessClient
from ecommerce.extensions.api.serializers import BusinessClientSerializer
from ecommerce.tests.testcases import TestCase


class ClientViewSetTests(TestCase):
    list_path = reverse('api:v2:clients-list')
    detail_path = reverse('api:v2:clients-detail')

    def setUp(self):
        super(ClientViewSetTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        self.name = 'TestClient'
        self.client = BusinessClient.objects.create(name=self.name)

    def test_create_client(self):
        """Verify a new client is created."""
        data = {'name': 'Test Client'}
        self.assertEqual(BusinessClient.objects.count(), 1)
        response = self.client.post(self.list_path, data=data, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.content['name'], data['name'])
        self.assertEqual(BusinessClient.objects.count(), 2)

    def test_list_clients(self):
        """Verify a list of clients is returned."""
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)
        results = response.content['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], BusinessClientSerializer(self.client))

    def test_client_details(self):
        """Verify details of a client are returned."""
        response = self.client.get(self.detail_path, kwargs={'pk': self.client.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, BusinessClientSerializer(self.client))

    def test_delete_client(self):
        """Verify a client is removed."""
        self.assertEqual(BusinessClient.objects.count(), 1)
        response = self.client.delete(self.list_path, kwargs={'pk': self.client.id})
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BusinessClient.objects.count(), 0)

        response = self.client.delete(self.list_path, kwargs={'pk': 23})
        self.assertEqual(response.status_code, 404)
