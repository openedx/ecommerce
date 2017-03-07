from django.core.management import call_command
from oscar.core.loading import get_model

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.testcases import TestCase

ProductClass = get_model('catalogue', 'ProductClass')

WRONG_SLUG = 'enrollment-code'
RIGHT_SLUG = 'enrollment_code'


class RemoveWrongProductClassTest(TestCase):
    def _create_product_class(self, slug):
        product_class, __ = ProductClass.objects.get_or_create(
            track_stock=False,
            requires_shipping=False,
            name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
            slug=slug,
        )
        return product_class

    def test_remove_product_class(self):
        """Faulty product class removed and products fixed."""
        faulty_product_class = self._create_product_class(WRONG_SLUG)
        product_class = self._create_product_class(RIGHT_SLUG)
        faulty_enrollment_code = ProductFactory(product_class=faulty_product_class)
        call_command('remove_wrong_product_class')

        faulty_enrollment_code.refresh_from_db()
        self.assertEqual(faulty_enrollment_code.product_class, product_class)
        self.assertFalse(ProductClass.objects.filter(slug=WRONG_SLUG).exists())

    def test_update_product_class(self):
        """Faulty product class updated."""
        faulty_product_class = self._create_product_class(WRONG_SLUG)
        faulty_enrollment_code = ProductFactory(product_class=faulty_product_class)
        call_command('remove_wrong_product_class')

        faulty_enrollment_code.refresh_from_db()
        faulty_product_class.refresh_from_db()
        self.assertEqual(faulty_enrollment_code.product_class.slug, RIGHT_SLUG)
        self.assertFalse(ProductClass.objects.filter(slug=WRONG_SLUG).exists())

    def test_no_actin(self):
        """Enrollment codes not updated."""
        product_class = self._create_product_class(RIGHT_SLUG)
        enrollment_code = ProductFactory(product_class=product_class)
        self.assertEqual(ProductClass.objects.count(), 1)
        call_command('remove_wrong_product_class')

        self.assertEqual(ProductClass.objects.count(), 1)
        enrollment_code.refresh_from_db()
        self.assertEqual(enrollment_code.product_class, product_class)
