import datetime

from oscar.core.loading import get_model

from oscar.test.factories import ProductFactory
from ecommerce.tests.testcases import TestCase

AttributeOption = get_model('catalogue', 'AttributeOption')
Catalog = get_model('catalogue', 'Catalog')
Course = get_model('courses', 'Course')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')


class EnrollmentCodeProductTest(TestCase):
    """ Testing the creation of an enrollment code product."""

    def test_enrollment_code_product(self):
        """
        Test if an enrollment code is properly created
        and has a course associated with it.
        """
        catalog = Catalog.objects.create(
            partner_id=self.partner.id
        )

        ec_product_class = ProductClass.objects.get(slug='enrollment_code')

        enrollment_code_product = ProductFactory(
            product_class=ec_product_class,
            title='Test product'
        )
        enrollment_code_type = AttributeOption.objects.get(option='single_use')

        enrollment_code_product.attr.catalog = catalog
        enrollment_code_product.attr.start_date = datetime.date(2016, 11, 30)
        enrollment_code_product.attr.end_date = datetime.date(2017, 11, 30)
        enrollment_code_product.attr.type = enrollment_code_type

        # clean() is an Oscar validation method for products
        self.assertIsNone(enrollment_code_product.clean())
