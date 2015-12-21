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

    def create_and_get_category(self, breadcrumb):
        """Create a category from breadcrumbs and return the API response for it."""
        create_from_breadcrumbs(breadcrumb)
        response = self.client.get(self.path)
        return json.loads(response.content)['results'][0]

    def test_category_list(self):
        """Test the reponse data for category."""
        response_content = self.create_and_get_category('Test')
        self.assertEqual(response_content['name'], 'Test')
        self.assertEqual(response_content['path'], '0001')
        self.assertEqual(response_content['depth'], 1)

    def test_sub_category_list(self):
        """Test the reponse data for sub-category."""
        response_content = self.create_and_get_category('Test > Sub-test')
        self.assertEqual(response_content['name'], 'Test')
        self.assertEqual(response_content['depth'], 1)
        self.assertEqual(response_content['child'][0]['name'], 'Sub-test')
        self.assertEqual(response_content['child'][0]['depth'], 2)
        self.assertEqual(response_content['child'][0]['path'], '00010001')

    def test_sub_sub_category_list(self):
        """Test the reponse data for sub-sub-category."""
        response_content = self.create_and_get_category('Test > Sub-test > Sub-sub-test')
        category = response_content['child'][0]['child'][0]
        self.assertEqual(category['name'], 'Sub-sub-test')
        self.assertEqual(category['depth'], 3)
        self.assertEqual(category['path'], '000100010001')
