import ddt
from django.core.management import call_command
from django.urls import reverse
from oscar.core.loading import get_model

from ecommerce.tests.testcases import TestCase

Category = get_model("catalogue", "Category")

TEST_CATEGORIES = ['Financial Assistance', 'Partner No Rev - RAP', 'Geography Promotion', 'Marketing Partner Promotion',
                   'Upsell Promotion', 'edX Employee Request', 'Course Promotion', 'Partner No Rev - ORAP',
                   'Services-Other', 'Partner No Rev - Upon Redemption', 'Bulk Enrollment - Prepay', 'Support-Other',
                   'ConnectEd', 'Marketing-Other', 'Affiliate Promotion', 'Retention Promotion',
                   'Partner No Rev - Prepay', 'Paid Cohort', 'Bulk Enrollment - Integration', 'On-Campus Learners',
                   'Security Disclosure Reward', 'Other', 'Customer Service', 'Bulk Enrollment - Upon Redemption',
                   'B2B Affiliate Promotion']


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
        self.assertEqual(response_data['count'], 25)
        received_coupon_categories = {category['name'] for category in response_data['results']}
        for category in TEST_CATEGORIES:
            self.assertTrue(category in received_coupon_categories)
