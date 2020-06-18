

from oscar.core.loading import get_model
from oscar.test.factories import ProductFactory

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')


class CourseEntitlementTest(TestCase):
    """ Test course entitlement products."""

    def test_course_entitlement_product(self):
        """Test if a course entitlement product is properly created."""

        product_class, _ = ProductClass.objects.get_or_create(name=COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME)
        product = ProductFactory(product_class=product_class)
        product.attr.UUID = '8724c585-acb2-42ab-986e-bc0847ef122c'
        product.attr.certificate_type = 'verified'
        product.attr.id_verification_required = False
        product.attr.save()

        product.refresh_from_db()
        self.assertEqual(product.attr.UUID, '8724c585-acb2-42ab-986e-bc0847ef122c')
        self.assertEqual(product.attr.certificate_type, 'verified')
        self.assertEqual(product.attr.id_verification_required, False)
