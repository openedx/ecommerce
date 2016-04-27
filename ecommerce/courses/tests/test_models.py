import json
import datetime
from requests import ConnectionError, Timeout

import ddt
import httpretty
import mock
import pytz

from oscar.core.loading import get_model
from oscar.test.factories import create_order
from oscar.test.newfactories import BasketFactory
from slumber.exceptions import SlumberBaseException

from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.models import Course
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.utils import get_default_seat_upgrade_deadline
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')


@ddt.ddt
class CourseTests(CourseCatalogTestMixin, TestCase):
    def setUp(self):
        """ Setup course and seats required to run tests """
        super(CourseTests, self).setUp()
        self.course = CourseFactory(name="Test Course")
        self.course_info = {'end': '2016-12-31T00:00:00Z'}

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
        self.assertEqual(self.course.products.count(), 1)
        self.assertEqual(len(self.course.seat_products), 0)

        # Create the seat products
        seats = [self.course.create_or_update_seat('honor', False, 0, self.partner),
                 self.course.create_or_update_seat('verified', True, 50, self.partner)]
        self.assertEqual(self.course.products.count(), 3)

        # The property should return only the child seats.
        self.assertEqual(set(self.course.seat_products), set(seats))

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
        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            self.course.publish_to_lms()
            self.assertTrue(mock_publish.called)

    def test_save_creates_parent_seat(self):
        """ Verify the save method creates a parent seat if one does not exist. """
        self.assertEqual(self.course.products.count(), 1)

        parent = self.course.parent_seat_product
        self.assertEqual(parent.structure, Product.PARENT)
        self.assertEqual(parent.title, 'Seat in Test Course')
        self.assertEqual(parent.get_product_class(), self.seat_product_class)
        self.assertEqual(parent.attr.course_key, self.course.id)

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

        # Test seat creation
        certificate_type = 'verified'
        id_verification_required = True
        price = 5
        course.create_or_update_seat(certificate_type, id_verification_required, price, self.partner)

        # Two seats: one verified, the other the parent seat product
        self.assertEqual(course.products.count(), 2)
        seat = course.seat_products[0]
        self.assert_course_seat_valid(seat, course, certificate_type, id_verification_required, price)

        # Test seat update
        price = 10
        course.create_or_update_seat(certificate_type, id_verification_required, price, self.partner)

        # Again, only two seats with one being the parent seat product.
        self.assertEqual(course.products.count(), 2)
        seat = course.seat_products[0]
        self.assert_course_seat_valid(seat, course, certificate_type, id_verification_required, price)

    def test_create_credit_seats(self):
        """Verify that the model's seat creation method allows the creation of multiple credit seats."""
        course = Course.objects.create(id='a/b/c', name='Test Course')
        credit_data = {'MIT': 2, 'Harvard': 0.5}
        certificate_type = 'credit'
        id_verification_required = True
        price = 10

        # Verify that the course can have multiple credit seats added to it
        for credit_provider, credit_hours in credit_data.iteritems():
            credit_seat = course.create_or_update_seat(
                certificate_type,
                id_verification_required,
                price,
                self.partner,
                credit_provider=credit_provider,
                credit_hours=credit_hours
            )

            self.assert_course_seat_valid(
                credit_seat,
                course,
                certificate_type,
                id_verification_required,
                price,
                credit_provider=credit_provider,
                credit_hours=credit_hours
            )

        # Expected seat total, with one being the parent seat product.
        self.assertEqual(course.products.count(), len(credit_data) + 1)

    def test_collision_avoidance(self):
        """
        Sanity check verifying that course IDs which produced collisions due to a
        lossy slug generation process no longer do so.
        """
        dotted_course = Course.objects.create(id='a/...course.../id')
        regular_course = Course.objects.create(id='a/course/id')

        certificate_type = 'honor'
        id_verification_required = False
        price = 0
        dotted_course.create_or_update_seat(certificate_type, id_verification_required, price, self.partner)
        regular_course.create_or_update_seat(certificate_type, id_verification_required, price, self.partner)

        child_products = Product.objects.filter(structure=Product.CHILD).count()
        self.assertEqual(child_products, 2)

    def test_prof_ed_stale_product_removal(self):
        """
        Verify that stale professional education seats are deleted if they have not been purchased.
        """
        self.course.create_or_update_seat('professional', False, 0, self.partner)
        self.assertEqual(self.course.products.count(), 2)

        self.course.create_or_update_seat('professional', True, 0, self.partner)
        self.assertEqual(self.course.products.count(), 2)

        product_mode = self.course.products.first()
        self.assertEqual(product_mode.attr.id_verification_required, True)
        self.assertEqual(product_mode.attr.certificate_type, 'professional')

    def test_prof_ed_stale_product_removal_with_orders(self):
        """
        Verify that professional education seats are never deleted if they have been purchased.
        """
        user = self.create_user()
        professional_product_no_verification = self.course.create_or_update_seat('professional', False, 0, self.partner)
        self.assertEqual(self.course.products.count(), 2)

        basket = BasketFactory(owner=user)
        basket.add_product(professional_product_no_verification)
        create_order(basket=basket, user=user)
        self.course.create_or_update_seat('professional', True, 0, self.partner)
        self.assertEqual(self.course.products.count(), 3)

        product_mode = self.course.products.all()[0]
        self.assertEqual(product_mode.attr.id_verification_required, True)
        self.assertEqual(product_mode.attr.certificate_type, 'professional')

        product_mode = self.course.products.all()[1]
        self.assertEqual(product_mode.attr.id_verification_required, False)
        self.assertEqual(product_mode.attr.certificate_type, 'professional')

    def test_create_or_update_seat_without_stale_seat_removal(self):
        """
        Verify that professional education seats are not deleted if remove_stale_modes flag is not set.
        """
        self.course.create_or_update_seat('professional', False, 0, self.partner)
        self.assertEqual(self.course.products.count(), 2)

        self.course.create_or_update_seat('professional', True, 0, self.partner, remove_stale_modes=False)
        self.assertEqual(self.course.products.count(), 3)

        product_mode = self.course.products.all()[0]
        self.assertEqual(product_mode.attr.id_verification_required, True)
        self.assertEqual(product_mode.attr.certificate_type, 'professional')

        product_mode = self.course.products.all()[1]
        self.assertEqual(product_mode.attr.id_verification_required, False)
        self.assertEqual(product_mode.attr.certificate_type, 'professional')

    def test_type(self):
        """ Verify the property returns a type value corresponding to the available products. """
        course = Course.objects.create(id='a/b/c', name='Test Course')
        self.assertEqual(course.type, 'audit')

        course.create_or_update_seat('audit', False, 0, self.partner)
        self.assertEqual(course.type, 'audit')

        course.create_or_update_seat('verified', True, 10, self.partner)
        self.assertEqual(course.type, 'verified')

        seat = course.create_or_update_seat('professional', True, 100, self.partner)
        self.assertEqual(course.type, 'professional')

        seat.delete()
        self.assertEqual(course.type, 'verified')
        course.create_or_update_seat('no-id-professional', False, 100, self.partner)
        self.assertEqual(course.type, 'professional')

        course.create_or_update_seat('credit', True, 1000, self.partner, credit_provider='SMU')
        self.assertEqual(course.type, 'credit')

    def mock_courses_api(self, status, body=None):
        """ Mock Courses API with specific status and body. """
        self.assertTrue(httpretty.is_enabled(), 'httpretty must be enabled to mock Course API calls.')

        body = body or {}
        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(self.course))
        httpretty.register_uri(
            httpretty.GET,
            course_url,
            status=status,
            body=json.dumps(body),
            content_type='application/json'
        )

    def mock_course_api_error(self, error):
        """ Mock Courses API with Error """

        def callback(request, uri, headers):  # pylint: disable=unused-argument
            raise error

        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(self.course))
        httpretty.register_uri(httpretty.GET, course_url, body=callback, content_type='application/json')

    @httpretty.activate
    def test_upgrade_deadline_with_default(self):
        """
        Given a course has an end date.
            Tests that if expires is NOT provided, it defaults the date to 10 days before course end.
            Test that if expires is provided, it do not use the default upgrade deadline and sets the
                seat expires to that date.
        """
        self.mock_courses_api(status=200, body=self.course_info)
        expires = datetime.datetime(2100, 1, 1, tzinfo=pytz.UTC)
        default_upgrade_deadline = get_default_seat_upgrade_deadline(self.course.id)

        # Create verified seat product with expires is not provided. Assert the expires should
        # default to 10 days before the course end.
        verified_seat = self.course.create_or_update_seat('verified', False, 500, self.partner)
        self.assertEqual(
            verified_seat.expires,
            default_upgrade_deadline,
            'Default expires should be 10 days before course end'
        )

        # Check it the seat expire is not set to default upgrade deadline
        # when expire date is provided.
        verified_seat = self.course.create_or_update_seat('verified', False, 500, self.partner, expires=expires)
        self.assertEqual(verified_seat.expires, expires, 'Default expires should be 10 days before course end')

    @httpretty.activate
    def test_upgrade_deadline_no_course_end(self):
        """
        Given course does not have end date
            Tests that when expires is NOT provided, it sets seat expires to None.
            Tests that when expires is provided, it sets seat expires to that date.
        """
        self.mock_courses_api(status=200, body={'end': None})
        expires = datetime.datetime(2100, 1, 1, tzinfo=pytz.UTC)

        # Create verified seat product with expires is not provided. Verify that expires is set to None.
        verified_seat = self.course.create_or_update_seat('verified', False, 500, self.partner)
        self.assertIsNone(verified_seat.expires, 'Default expires should be 10 days before course end')

        # Create/Update verified seat product
        verified_seat = self.course.create_or_update_seat('verified', False, 500, self.partner, expires=expires)
        self.assertEqual(verified_seat.expires, expires, 'Default expires should be 10 days before course end')

    @ddt.data(ConnectionError, SlumberBaseException, Timeout)
    @mock.patch('ecommerce.courses.utils.logger')
    @httpretty.activate
    def test_get_default_seat_upgrade_deadline_failure(self, error, mock_logger):
        """ Verify a connection error and timeout are logged when they happen. """
        self.mock_course_api_error(error)
        verified_seat = self.course.create_or_update_seat('verified', False, 500, self.partner)
        self.assertTrue(mock_logger.exception.called)
        mock_logger.exception.assert_called_once_with(
            'Failed to retrieve data from Course API for course [%s].',
            self.course.id
        )
        # Verify that seat expires has not been updated.
        self.assertIsNone(verified_seat.expires, 'Expires is somehow initilised .')
