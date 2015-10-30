import datetime
from django.test import TestCase
from oscar.core.loading import get_model

Catalog = get_model('catalogue', 'Catalog')
Course = get_model('courses', 'Course')
Partner = get_model('partner', 'Partner')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')


class EnrollmentCodeProduct(TestCase):
    """ Testing the creation of an enrollment code product."""

    def setUp(self):
        self.partner = Partner.objects.get(short_code='edX')
        self.catalog = Catalog.objects.create(
            partner_id=self.partner.id
        )
        self.course = Course.objects.create(
            id='org/number/run',
            name='Test course'
        )
        self.catalog.courses.add(self.course)
        self.ec_product_class = ProductClass.objects.get(slug='enrollment_code')

    def test_enrollment_code_product(self):
        """
        Test if an enrollment code is properly created
        and has a course associated with it.
        """
        enrollment_code_product = Product.objects.create(
            product_class=self.ec_product_class,
            title='Test product',

        )
        enrollment_code_product.attr.catalog = self.catalog
        enrollment_code_product.attr.start_date = datetime.date(2016, 11, 30)
        enrollment_code_product.attr.end_date = datetime.date(2017, 11, 30)
        # clean() is an Oscar validation method for products
        self.assertIsNone(enrollment_code_product.clean())
        self.assertEqual(enrollment_code_product.attr.catalog.courses.count(), 1)
