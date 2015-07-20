from hashlib import md5

from django.test import TestCase
from ecommerce.courses.models import Course

from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.catalogue.utils import generate_sku


class UtilsTests(CourseCatalogTestMixin, TestCase):
    def test_generate_sku_for_course_seat(self):
        """Verify the method generates a SKU for a course seat."""
        course_id = 'sku/test/course'
        course = Course.objects.create(id=course_id, name='Test Course')
        certificate_type = 'honor'
        product = course.create_or_update_seat(certificate_type, False, 0)

        _hash = md5(u'{} {} {}'.format(certificate_type, course_id, 'False')).hexdigest()[-7:]
        expected = _hash.upper()
        actual = generate_sku(product)
        self.assertEqual(actual, expected)
