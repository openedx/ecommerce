import ddt
from django.test import TestCase
from django_dynamic_fixture import G
import mock
from oscar.core.loading import get_model

from ecommerce.courses.models import Course
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')


@ddt.ddt
class CourseTests(CourseCatalogTestMixin, TestCase):
    def test_unicode(self):
        """Verify the __unicode__ method returns the Course ID."""
        course_id = u'edx/Demo_Course/DemoX'
        course = Course.objects.create(id=course_id)
        self.assertEqual(unicode(course), course_id)

    def test_seat_products(self):
        """
        Verify the method returns a list containing purchasable course seats.

        These seats should be the child products.
        """
        # Create a new course and verify it has a parent product, but no children.
        course = G(Course)
        self.assertEqual(course.products.count(), 1)
        self.assertEqual(len(course.seat_products), 0)

        # Create the seat products
        seats = [course.create_or_update_seat('honor', False, 0),
                 course.create_or_update_seat('verified', True, 50)]
        self.assertEqual(course.products.count(), 3)

        # The property should return only the child seats.
        self.assertEqual(set(course.seat_products), set(seats))

    @ddt.data(
        ('verified', True),
        ('credit', True),
        ('professional', True),
        ('honor', False),
        ('no-id-professional', False),
        ('audit', False),
        ('unknown', False),
    )
    @ddt.unpack
    def test_is_mode_verified(self, mode, expected):
        """ Verify the method returns True only for verified modes. """
        self.assertEqual(Course.is_mode_verified(mode), expected)

    @ddt.data(
        ('Verified', 'verified'),
        ('credit', 'credit'),
        ('professional', 'professional'),
        ('honor', 'honor'),
        ('no-id-professional', 'professional'),
        ('audit', ''),
        ('unknown', 'unknown'),
    )
    @ddt.unpack
    def test_certificate_type_for_mode(self, mode, expected):
        """ Verify the method returns the correct certificate type for a given mode. """
        self.assertEqual(Course.certificate_type_for_mode(mode), expected)

    def test_publish_to_lms(self):
        """ Verify the method publishes data to LMS. """
        course = G(Course)
        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            course.publish_to_lms()
            self.assertTrue(mock_publish.called)

    def test_save_creates_parent_seat(self):
        """ Verify the save method creates a parent seat if one does not exist. """
        course = Course.objects.create(id='a/b/c', name='Test Course')
        self.assertEqual(course.products.count(), 1)

        parent = course.parent_seat_product
        self.assertEqual(parent.structure, Product.PARENT)
        self.assertEqual(parent.title, 'Seat in Test Course')
        self.assertEqual(parent.get_product_class(), self.seat_product_class)
        self.assertEqual(parent.attr.course_key, course.id)

    def assert_course_seat_valid(self, seat, course, certificate_type, id_verification_required, price,
                                 credit_provider=None, credit_hours=None):
        """ Ensure the given seat has the correct attribute values. """
        self.assertEqual(seat.structure, Product.CHILD)
        # pylint: disable=protected-access
        self.assertEqual(seat.title, course._get_course_seat_name(certificate_type, id_verification_required))
        self.assertEqual(seat.get_product_class(), self.seat_product_class)
        self.assertEqual(getattr(seat.attr, 'certificate_type', ''), certificate_type)
        self.assertEqual(seat.attr.course_key, course.id)
        self.assertEqual(seat.attr.id_verification_required, id_verification_required)
        self.assertEqual(seat.stockrecords.first().price_excl_tax, price)

        if credit_provider:
            self.assertEqual(seat.attr.credit_provider, credit_provider)

        if credit_hours:
            self.assertEqual(seat.attr.credit_hours, credit_hours)

    def test_create_or_update_seat(self):
        """ Verify the method creates or updates a seat Product. """
        course = Course.objects.create(id='a/b/c', name='Test Course')

        # Test creation
        certificate_type = 'honor'
        id_verification_required = True
        price = 0
        course.create_or_update_seat(certificate_type, id_verification_required, price)

        # Two seats: one honor, the other the parent seat product
        self.assertEqual(course.products.count(), 2)
        seat = course.seat_products[0]
        self.assert_course_seat_valid(seat, course, certificate_type, id_verification_required, price)

        # Test update
        price = 100
        credit_provider = 'MIT'
        credit_hours = 2
        course.create_or_update_seat(
            certificate_type, id_verification_required, price, credit_provider, credit_hours=credit_hours
        )

        # Again, only two seats with one being the parent seat product.
        self.assertEqual(course.products.count(), 2)
        seat = course.seat_products[0]
        self.assert_course_seat_valid(
            seat, course, certificate_type, id_verification_required, price, credit_provider, credit_hours=credit_hours
        )

    def test_type(self):
        """ Verify the property returns a type value corresponding to the available products. """
        course = Course.objects.create(id='a/b/c', name='Test Course')
        self.assertEqual(course.type, 'honor')

        course.create_or_update_seat('honor', False, 0)
        self.assertEqual(course.type, 'honor')

        course.create_or_update_seat('verified', True, 10)
        self.assertEqual(course.type, 'verified')

        seat = course.create_or_update_seat('professional', True, 100)
        self.assertEqual(course.type, 'professional')

        seat.delete()
        self.assertEqual(course.type, 'verified')
        course.create_or_update_seat('no-id-professional', False, 100)
        self.assertEqual(course.type, 'professional')

        course.create_or_update_seat('credit', True, 1000, credit_provider='SMU')
        self.assertEqual(course.type, 'credit')
