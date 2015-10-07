import ddt
from django.test import TestCase
from ecommerce.enrollmentcodes.models import EnrollmentCode


class EnrollmentcodesTests(TestCase):
    def test(self):
        self.assertEqual(1, 1)

    def test_saving(self):
        enrollment_code = EnrollmentCode.objects.create(
            course_id='Test/TS/run',
            code='ECCODE1',
            price=100
        )
        self.assertEqual(enrollment_code.objects.count(), 1)
