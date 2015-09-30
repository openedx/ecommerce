import ddt

from django.test import TestCase

from ecommerce.courses.models import Course
from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.mixins import PartnerMixin


@ddt.ddt
class UtilsTests(CourseCatalogTestMixin, PartnerMixin, TestCase):
    @ddt.unpack
    @ddt.data(
        ('', False, 'audit'),
        ('honor', True, 'honor'),
        ('honor', False, 'honor'),
        ('verified', True, 'verified'),
        ('verified', False, 'verified'),
        ('professional', True, 'professional'),
        ('professional', False, 'no-id-professional'),
        ('no-id-professional', False, 'no-id-professional'),
    )
    def test_mode_for_seat(self, certificate_type, id_verification_required, mode):
        """ Verify the correct enrollment mode is returned for a given seat. """
        course = Course.objects.create(id='edx/Demo_Course/DemoX')
        partner = self.create_partner('edx')
        seat = course.create_or_update_seat(certificate_type, id_verification_required, 10.00, partner)
        self.assertEqual(mode_for_seat(seat), mode)
