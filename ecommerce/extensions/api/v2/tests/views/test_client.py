""" Tests for client API endpoint. """
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from django.core.urlresolvers import reverse

from ecommerce.core.models import BusinessClient
from ecommerce.extensions.api.serializers import BusinessClientSerializer
from ecommerce.tests.testcases import TestCase


class ClientViewSetTests(TestCase):
    list_path = reverse('api:v2:clients-list')

    def setUp(self):
        super(ClientViewSetTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        self.name = 'TestClient'
        self.business_client = BusinessClient.objects.create(name=self.name)
        self.details_path = reverse('api:v2:clients-detail', args=[self.business_client.id])

    def test_authentication_required(self):
        """Test that a guest cannot access the view."""
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 401)

    def test_authorization_required(self):
        """Test that a non-staff user cannot access the view."""
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)

        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 403)

    def test_create_client(self):
        """Verify a new client is created."""
        data = {'name': 'Test Client'}
        self.assertEqual(BusinessClient.objects.count(), 1)
        response = self.client.post(self.list_path, data=data, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.content)['name'], data['name'])
        self.assertEqual(BusinessClient.objects.count(), 2)

    def test_list_clients(self):
        """Verify a list of clients is returned."""
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)
        results = json.loads(response.content)['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], BusinessClientSerializer(self.business_client).data)

    def test_client_details(self):
        """Verify details of a client are returned."""
        response = self.client.get(self.details_path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), BusinessClientSerializer(self.business_client).data)

    def test_delete_client(self):
        """Verify a client is removed."""
        self.assertEqual(BusinessClient.objects.count(), 1)
        response = self.client.delete(self.details_path)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(BusinessClient.objects.count(), 0)

        invalid_client_path = reverse('api:v2:clients-detail', args=[123])
        response = self.client.delete(invalid_client_path)
        self.assertEqual(response.status_code, 404)

    def test_name_filtering(self):
        """Verify filtering clients by name."""
        invalid_path = '{}?name=invalid'.format(self.list_path)
        response = self.client.get(invalid_path)
        self.assertEqual(json.loads(response.content)['count'], 0)

        path = '{}?name={}'.format(self.list_path, self.business_client.name)
        response = self.client.get(path)
        self.assertEqual(json.loads(response.content)['count'], 1)
