import ddt
from django.test import TestCase

from ecommerce.enrollmentcodes.models import EnrollmentCode
from ecommerce.extensions.order.models import Order
from ecommerce.tests.mixins import UserMixin


class EnrollmentcodesTests(UserMixin, TestCase):

    def test_saving(self):
        """Verify the method saves the objects properly. """
        # Create a new user and order which are using in the save method
        user = self.create_user()
        order = Order.objects.create(
            number=1,
            total_incl_tax=10,
            total_excl_tax=10
        )
        # Create the enrollment code object
        enrollment_code = EnrollmentCode.objects.create(
            course_id='Test/TS/run',
            code='ECCODE1',
            price=100,
            created_by_id=user,
            order_id=order
        )

        self.assertEqual(EnrollmentCode.objects.count(), 1)
        self.assertEqual(enrollment_code.code, 'ECCODE1')
