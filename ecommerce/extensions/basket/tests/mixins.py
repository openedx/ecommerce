from oscar.core.loading import get_class, get_model
from oscar.test import factories

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.tests.mixins import SiteMixin

Default = get_class('partner.strategy', 'Default')
Basket = get_model('basket', 'Basket')
Product = get_model('catalogue', 'Product')


class BasketMixin(SiteMixin):
    def create_basket(self, owner, site, status=Basket.OPEN, empty=False):
        owner = owner or factories.UserFactory()
        site = site or self.site
        basket = Basket.objects.create(owner=owner, site=site, status=status)
        basket.strategy = Default()
        if not empty:
            product = factories.create_product()
            factories.create_stockrecord(product, num_in_stock=2)
            basket.add_product(product)
        return basket

    def prepare_course_seat_and_enrollment_code(self, seat_type='verified', id_verification=False):
        """
        Helper function that creates a new course, enables enrollment codes and creates a new
        seat and enrollment code for it.

        Args:
            seat_type (str): Seat/certification type.
            is_verification (bool): Whether or not id verification is required for the seat.
        Returns:
            The newly created course, seat and enrollment code.
        """
        course = CourseFactory(partner=self.partner)
        seat = course.create_or_update_seat(seat_type, id_verification, 10, create_enrollment_code=True)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        return course, seat, enrollment_code
