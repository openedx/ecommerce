from __future__ import unicode_literals

import logging

from oscar.core.loading import get_model
from oscar.core.utils import slugify
from oscar.test import factories

from ecommerce.core.constants import (
    ENROLLMENT_CODE_PRODUCT_CLASS_NAME,
    ENROLLMENT_CODE_SWITCH,
    SEAT_PRODUCT_CLASS_NAME
)
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.tests.factories import PartnerFactory

logger = logging.getLogger(__name__)

Category = get_model('catalogue', 'Category')
Partner = get_model('partner', 'Partner')
Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')


class DiscoveryTestMixin(object):
    """
    Mixin for all tests involving the course catalog or course seats.

    The setup method guarantees the requisite product class, partner, and category will be in place. This is especially
    useful when running tests without database migrations (which normally create these objects).
    """

    def setUp(self):
        super(DiscoveryTestMixin, self).setUp()

        # Force the creation of a seat ProductClass
        self.seat_product_class  # pylint: disable=pointless-statement
        self.enrollment_code_product_class  # pylint: disable=pointless-statement

        category_name = 'Seats'
        try:
            self.category = Category.objects.get(name=category_name)
        except Category.DoesNotExist:
            self.category = factories.CategoryFactory(name=category_name)

    def create_course_and_seat(
            self, course_id=None, seat_type='verified', id_verification=False, price=10, partner=None
    ):
        """
        Create a course and a seat from that course.

        Arguments:
            course_name (str): name of the course
            seat_type (str): the seat type
            id_verification (bool): if id verification is required
            price (int): seat price
            partner(Partner): the site partner

        Returns:
            The created course and seat.
        """

        if not partner:
            partner = PartnerFactory()
        if not course_id:
            course = CourseFactory()
        else:
            course = CourseFactory(id=course_id)

        seat = course.create_or_update_seat(seat_type, id_verification, price, partner)
        return course, seat

    def _create_product_class(self, class_name, slug, attributes):
        """ Helper method for creating product classes.

        Args:
            class_name (str): Name of the product class.
            slug (str): Slug of the product class.
            attributes (tuple): Tuple of tuples where each contains attribute name and type.

        Returns:
            ProductClass object.
        """

        defaults = {'requires_shipping': False, 'track_stock': False, 'name': class_name}
        pc, created = ProductClass.objects.get_or_create(slug=slug, defaults=defaults)

        if created:
            for code, attr_type in attributes:
                factories.ProductAttributeFactory(code=code, name=code, product_class=pc, type=attr_type)

        return pc

    @property
    def seat_product_class(self):
        attributes = (
            ('certificate_type', 'text'),
            ('course_key', 'text'),
            ('credit_provider', 'text'),
            ('id_verification_required', 'boolean'),
            ('credit_hours', 'integer'),
        )
        product_class = self._create_product_class(
            SEAT_PRODUCT_CLASS_NAME, slugify(SEAT_PRODUCT_CLASS_NAME), attributes
        )
        return product_class

    @property
    def enrollment_code_product_class(self):
        attributes = (
            ('seat_type', 'text'),
            ('course_key', 'text'),
            ('id_verification_required', 'boolean')
        )
        product_class = self._create_product_class(
            ENROLLMENT_CODE_PRODUCT_CLASS_NAME, 'enrollment_code', attributes
        )
        return product_class

    def create_course_seat_and_enrollment_code(
            self, seat_type='verified', price=10, id_verification=False, expires=None
    ):
        """
        Create a new course, seat and enrollment code.
        In order to create an enrollment code the waffle switch and site configuration
        value for enrollment codes need to be turned on.

        Args:
            seat_type (str): Seat type.
            price (int): Seat price.
            id_verification (bool): Whether or not an ID verification is necessary for the seat.
            expires (datetime): Seat and enrollment code expiration date.
        Returns:
            The newly created course, seat and enrollment code.
        """
        course = CourseFactory()
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)
        site_configuration = self.site.siteconfiguration
        site_configuration.enable_enrollment_codes = True
        site_configuration.save()

        seat = course.create_or_update_seat(
            seat_type, id_verification, price, self.partner, expires=expires, create_enrollment_code=True
        )
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        return course, seat, enrollment_code
