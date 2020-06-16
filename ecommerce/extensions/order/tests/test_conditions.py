

from django.test import RequestFactory
from django.urls import reverse
from mock import patch
from oscar.test.factories import BasketFactory

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.test.factories import (
    EnterpriseOfferFactory,
    ManualEnrollmentOrderDiscountConditionFactory,
    ManualEnrollmentOrderOfferFactory
)
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.testcases import TestCase


class ManualEnrollmentOrderDiscountConditionTests(TestCase):
    """
    Test the `ManualEnrollmentOrderDiscountCondition` functionality.
    """
    def setUp(self):
        super(ManualEnrollmentOrderDiscountConditionTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.learner = self.create_user(username='learner', is_staff=False)
        self.condition = ManualEnrollmentOrderDiscountConditionFactory()
        self.basket = BasketFactory(site=self.site, owner=self.learner)
        self.course = CourseFactory(id='course-v1:MAX+CX+Course', partner=self.partner)
        self.course.create_or_update_seat(
            certificate_type='verified',
            id_verification_required=True,
            price=50
        )
        self.course.create_or_update_seat(
            certificate_type='audit',
            id_verification_required=False,
            price=0
        )
        self.seat_product = self.course.seat_products.filter(
            attributes__name='certificate_type'
        ).exclude(
            attribute_values__value_text='audit'
        ).first()

        request_patcher = patch('crum.get_current_request')
        self.request_patcher = request_patcher.start()
        self.request_patcher.return_value = RequestFactory().post(
            reverse('api:v2:manual-course-enrollment-order-list')
        )
        self.addCleanup(request_patcher.stop)

    def test_is_satisfied_with_wrong_offer(self):
        """
        Test `ManualEnrollmentOrderDiscountCondition.is_satisfied` works as expected for wrong offer.
        """
        offer = EnterpriseOfferFactory(partner=self.partner, condition=self.condition)
        status = self.condition.is_satisfied(offer, self.basket)
        assert not status

    def test_is_satisfied_with_wrong_order_lines(self):
        """
        Test `ManualEnrollmentOrderDiscountCondition.is_satisfied` works as expected when there wrong
        number of order lines.
        """
        for seat_product in self.course.seat_products:
            self.basket.add_product(seat_product)

        offer = ManualEnrollmentOrderOfferFactory()
        status = self.condition.is_satisfied(offer, self.basket)
        assert not status

    def test_is_satisfied_with_non_seat_type_product(self):
        """
        Test `ManualEnrollmentOrderDiscountCondition.is_satisfied` works as expected when there basket contains
        non seat type product.
        """
        product = ProductFactory()
        self.basket.add_product(product)

        offer = ManualEnrollmentOrderOfferFactory()
        status = self.condition.is_satisfied(offer, self.basket)
        assert not status

    def test_is_satisfied_with_non_verified_seat_type_product(self):
        """
        Test `ManualEnrollmentOrderDiscountCondition.is_satisfied` works as expected when there basket contains
        seat type product but seat is not verified.
        """
        seat_product = self.course.seat_products.filter(
            attribute_values__value_text='audit'
        ).first()

        self.basket.add_product(seat_product)

        offer = ManualEnrollmentOrderOfferFactory()
        status = self.condition.is_satisfied(offer, self.basket)
        assert not status

    def test_is_satisfied_success(self):
        """
        Test `ManualEnrollmentOrderDiscountCondition.is_satisfied` works as expected when condition satisfies.
        """
        self.basket.add_product(self.seat_product)
        offer = ManualEnrollmentOrderOfferFactory()
        status = self.condition.is_satisfied(offer, self.basket)
        assert status

    def test_is_satisfied_with_wrong_path_info(self):
        """
        Test `ManualEnrollmentOrderDiscountCondition.is_satisfied` works as expected when request path_info is wrong.
        """
        with patch('crum.get_current_request') as request_patcher:
            request_patcher.return_value = RequestFactory().post('some_view_path')
            offer = ManualEnrollmentOrderOfferFactory()
            self.basket.add_product(self.seat_product)
            status = self.condition.is_satisfied(offer, self.basket)
            assert not status
