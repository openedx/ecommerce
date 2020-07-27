import ddt
from django.core.management import call_command
from oscar.core.loading import get_model

from ecommerce.tests.testcases import TestCase

Category = get_model("catalogue", "Category")


@ddt.ddt
class CreateCategoriesFromBreadcrumbsTests(TestCase):
    """Tests for create_categories_from_breadcrumbs management command."""

    @ddt.unpack
    @ddt.data(
        ("Coupon", 'Affiliate Promotion',),
        ("Coupon", 'Bulk Enrollment'),
        ("Coupon", 'ConnectEd'),
        ("Coupon", 'Course Promotion')
    )
    def test_create_categories_from_breadcrumbs(self, parent, child):
        """Test that command logs no offer needs to be changed."""
        call_command('create_categories_from_breadcrumbs', parent, child)

        category = Category.objects.get(name=parent).get_children().filter(
            name=child
        )
        self.assertEqual(1, category.count())
