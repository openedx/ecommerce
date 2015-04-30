from hashlib import md5

from django.test import TestCase

from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.catalogue.utils import generate_sku


class UtilsTests(CourseCatalogTestMixin, TestCase):
    def test_generate_sku_for_course_seat(self):
        """Verify the method generates a SKU for a course seat."""
        course_id = 'sku/test/course'
        certificate_type = 'honor'
        product = self.create_course_seats(course_id, [certificate_type])[certificate_type]

        _hash = md5(u'{} {}'.format(certificate_type, course_id)).hexdigest()[-7:]
        expected = _hash.upper()
        actual = generate_sku(product)
        self.assertEqual(actual, expected)
