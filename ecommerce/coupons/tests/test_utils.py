import ddt

from ecommerce.coupons.utils import prepare_course_seat_types
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class CouponAppViewTests(TestCase):

    @ddt.data(
        (['verIfiEd', 'profeSSional'], 'verified,professional'),
        (None, None)
    )
    @ddt.unpack
    def test_prepare_course_seat_types(self, course_seat_types, expected_result):
        """Verify prepare course seat types return correct value."""
        self.assertEqual(prepare_course_seat_types(course_seat_types), expected_result)
