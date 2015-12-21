from __future__ import unicode_literals

import json

from django.core.urlresolvers import reverse
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model

from ecommerce.tests.testcases import TestCase

Category = get_model('catalogue', 'Category')


class CategoryViewSetTests(TestCase):
    """Test the category API endpoint listing."""
    path = reverse('api:v2:categories-list')

    def setUp(self):
        super(CategoryViewSetTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        Category.objects.all().delete()

    def create_category_get_response(self, breadcrumb):
        """Create a category from breadcrumbs and return the API response for it."""
        create_from_breadcrumbs(breadcrumb)
        response = self.client.get(self.path)
        return json.loads(response.content)['results'][0]

    def test_category_list(self):
        """Test the reponse data for category."""
        response_content = self.create_category_get_response('Test')
        self.assertEqual(response_content['name'], 'Test')
        self.assertEqual(response_content['path'], '0001')
        self.assertEqual(response_content['depth'], 1)

    def test_category_filtering(self):
        create_from_breadcrumbs('Test')
        category = create_from_breadcrumbs('Test2')
        self.assertEqual(Category.objects.count(), 2)

        filter_path = '{}?depth=1&path={}'.format(self.path, category.path)
        response = self.client.get(filter_path)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['count'], 1)
        self.assertEqual(response_content['results'][0]['name'], 'Test2')
