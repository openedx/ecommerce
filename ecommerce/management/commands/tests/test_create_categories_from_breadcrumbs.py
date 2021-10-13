import os

import ddt
from django.core.management import call_command
from django.urls import reverse
from oscar.core.loading import get_model

from ecommerce.tests.testcases import TestCase

Category = get_model("catalogue", "Category")
DEPRECATED_COUPON_CATEGORIES = ['Bulk Enrollment']

current_dir = os.path.dirname(__file__)
rel_path = 'coupon_category_list.txt'
full_path = os.path.join(current_dir, '..', rel_path)

with open(full_path) as f:
    DEFAULT_CATEGORIES = f.read().splitlines()
f.close()


@ddt.ddt
class CreateCategoriesFromBreadcrumbsTests(TestCase):
    """Tests for create_categories_from_breadcrumbs management command."""
    path = reverse('api:v2:coupons:coupons_categories')

    def test_category_list(self):
        """ Verify the endpoint returns successfully. """
        # Create default categories
        call_command('create_categories_from_breadcrumbs')

        response = self.client.get(self.path + '?page_size=200')
        response_data = response.json()
        self.assertEqual(response_data['count'], 26)
        received_coupon_categories = {category['name'] for category in response_data['results']}

        for category in DEFAULT_CATEGORIES:
            if category not in DEPRECATED_COUPON_CATEGORIES:
                self.assertTrue(category in received_coupon_categories)
