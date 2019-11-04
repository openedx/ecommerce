"""HTTP endpoints for interacting with orders."""
from __future__ import absolute_import

import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.decorators import method_decorator
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from oscar.core.loading import get_class, get_model
from rest_framework import filters, status, viewsets
from rest_framework.decorators import detail_route
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import DjangoModelPermissions, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from ecommerce.courses.models import Course
from ecommerce.extensions.analytics.utils import audit_log
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.filters import OrderFilter
from ecommerce.extensions.api.permissions import IsStaffOrOwner
from ecommerce.extensions.api.throttles import ServiceUserThrottle
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.fulfillment.status import LINE, ORDER
from ecommerce.extensions.offer.models import OFFER_PRIORITY_MANUAL_ORDER
from ecommerce.extensions.order.benefits import ManualEnrollmentOrderDiscountBenefit
from ecommerce.extensions.order.conditions import ManualEnrollmentOrderDiscountCondition
from ecommerce.programs.custom import class_path

logger = logging.getLogger(__name__)

Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
post_checkout = get_class('checkout.signals', 'post_checkout')
Basket = get_model('basket', 'Basket')
Applicator = get_class('offer.applicator', 'Applicator')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
Condition = get_model('offer', 'Condition')
Benefit = get_model('offer', 'Benefit')


@method_decorator(transaction.non_atomic_requests, name='dispatch')
class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = 'number'
    permission_classes = (IsAuthenticated, IsStaffOrOwner, DjangoModelPermissions,)
    queryset = Order.objects.all()
    serializer_class = serializers.OrderSerializer
    throttle_classes = (ServiceUserThrottle,)
    filter_backends = (filters.DjangoFilterBackend,)
    filter_class = OrderFilter

    def filter_queryset(self, queryset):
        queryset = super(OrderViewSet, self).filter_queryset(queryset)

        username = self.request.query_params.get('username')
        user = self.request.user

        # Non-staff users should only see their own orders
        if not user.is_staff:
            if username and user.username != username:
                raise PermissionDenied

            queryset = queryset.filter(user=user)

        return queryset.filter(partner=self.request.site.siteconfiguration.partner)

    @detail_route(methods=['put', 'patch'])
    def fulfill(self, request, number=None):  # pylint: disable=unused-argument
        """ Fulfill order """
        order = self.get_object()

        if not order.is_fulfillable:
            return Response(status=status.HTTP_406_NOT_ACCEPTABLE)

        # Get email_opt_in from the query parameters if it exists, defaulting to false
        email_opt_in = request.query_params.get('email_opt_in', False) == 'True'

        logger.info('Attempting fulfillment of order [%s]...', order.number)
        with transaction.atomic():
            post_checkout.send(
                sender=post_checkout,
                order=order,
                request=request,
                email_opt_in=email_opt_in,
            )

        if order.is_fulfillable:
            logger.warning('Fulfillment of order [%s] failed!', order.number)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = self.get_serializer(order)
        return Response(serializer.data)


class ManualCourseEnrollmentOrderViewSet(EdxOrderPlacementMixin, ViewSet):
    """
        **Use Cases**

            API to create basket/order for learners manually enrolled in to
            a course but they have paid the course price outside of the ecommerce.

        **Behavior**

            Implements POST action only.

            POST /api/v2/manual_course_enrollment_order/
            >>> {
            >>>     "enrollments": [
            >>>         {
            >>>             "lms_user_id": 111,
            >>>             "username": "me",
            >>>             "email": "me@example.com",
            >>>             "course_run_key": "course-v1:TestX+Test100+2019_T1"
            >>>         },
            >>>         {
            >>>             "lms_user_id": 123,
            >>>             "username": "metoo",
            >>>             "email": "metoo@example.com",
            >>>             "course_run_key": ""
            >>>         },
            >>>     ]
            >>> }

            Response
            >>> {
            >>>     "orders": [
            >>>         {
            >>>             "lms_user_id": 111,
            >>>             "username": "me",
            >>>             "email": "me@example.com",
            >>>             "course_run_key": "course-v1:TestX+Test100+2019_T1",
            >>>             "status": "success",
            >>>             "detail": "EDX-123456"
            >>>         },
            >>>         {
            >>>             "lms_user_id": 123,
            >>>             "username": "metoo",
            >>>             "email": "metoo@example.com",
            >>>             "course_run_key": ""
            >>>             "status": "failure",
            >>>             "detail": "Missing required enrollmment data: `course_run_key`"
            >>>         },
            >>>     ]
            >>> }
    """

    authentication_classes = (JwtAuthentication,)
    permission_classes = (IsAuthenticated, IsAdminUser)
    http_method_names = ['post']

    SUCCESS, FAILURE = "success", "failure"

    def create(self, request):
        """
        Will recieve enrollments in the format specified in the class definition.
        *lms_user_id*
            LMS user id.
        *username*
            Learner username who is manually enrolled in course and for this learner basket/order will be created.
        *email*
            Learner email.
        *course_run_key*
            Course in which learner is enrolled.
        """

        try:
            enrollments = request.data["enrollments"]
        except KeyError:
            return Response(
                {
                    "status": "failure",
                    "detail": "Invalid data. No `enrollments` field."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        orders = []
        for enrollment in enrollments:
            orders.append(self._create_single_order(enrollment, request.user, request.site))

        return Response({"orders": orders}, status=status.HTTP_200_OK)

    def _create_single_order(self, enrollment, request_user, request_site):
        """
            Creates an order from a single enrollment.
            Params:
                `enrollment`: <dict> with fields:
                    "lms_user_id": <int>,
                    "username": <string>,
                    "email": <string>,
                    "course_run_key": <string>
                `request_user`: <User>
                `request_site`: <Site>
            Returns:
                `enrollment` from above with the additional fields:
                    "status": <string> ("success" or "failure")
                    "detail": <string> (order number if success, otherwise failure reason)
        """
        try:
            (
                lms_user_id,
                learner_username,
                learner_email,
                course_run_key,
            ) = self._get_required_enrollment_data(enrollment)
        except ValidationError as ex:
            return dict(enrollment, status=self.FAILURE, detail=ex.message)

        logger.info(
            '[Manual Order Creation] Request received. User: %s, Email: %s, Course: %s, RequestUser: %s',
            learner_username,
            learner_email,
            course_run_key,
            request_user.username,
        )

        learner_user = self._get_learner_user(lms_user_id, learner_username, learner_email)

        try:
            course = Course.objects.get(id=course_run_key)
        except Course.DoesNotExist:
            return dict(enrollment, status=self.FAILURE, detail="Course not found")

        seat_product = course.seat_products.filter(
            attributes__name='certificate_type'
        ).exclude(
            attribute_values__value_text='audit'
        ).first()

        # check if an order already exists with the requested data
        order_line = OrderLine.objects.filter(product=seat_product, order__user=learner_user, status=LINE.COMPLETE)
        if order_line.exists():
            return dict(
                enrollment,
                status=self.SUCCESS,
                detail=Order.objects.get(id=order_line.first().order_id).number
            )

        basket = Basket.create_basket(request_site, learner_user)
        basket.add_product(seat_product)

        discount_offer = self._get_or_create_discount_offer()
        Applicator().apply_offers(basket, [discount_offer])
        try:
            order = self.place_free_order(basket)
        except:  # pylint: disable=bare-except
            logger.exception(
                '[Manual Order Creation Failure] Failed to place the order. User: %s, Course: %s, Basket: %s, '
                'Product: %s',
                learner_user.username,
                course.id,
                basket.id,
                seat_product.id,
            )
            return dict(enrollment, status=self.FAILURE, detail="Failed to create free order")

        logger.info(
            '[Manual Order Creation] Order completed. User: %s, Course: %s, Basket: %s, Order: %s, Product: %s',
            learner_user.username,
            course.id,
            basket.id,
            seat_product.id,
            order.number,
        )
        return dict(enrollment, status=self.SUCCESS, detail=order.number)

    def _get_required_enrollment_data(self, enrollment):
        """
        Return required parameters from incoming enrollment.

        Raises:
            ValidationError: If any required parameter is not present in enrollment.
        """
        lms_user_id = enrollment.get('lms_user_id')
        learner_username = enrollment.get('username')
        learner_email = enrollment.get('email')
        course_run_key = enrollment.get('course_run_key')
        if not (lms_user_id and learner_username and learner_email and course_run_key):
            enrollment_parameters_state = [
                ("'lms_user_id'", bool(lms_user_id)),
                ("'username'", bool(learner_username)),
                ("'email'", bool(learner_email)),
                ("'course_run_key'", bool(course_run_key)),
            ]
            missing_params = ', '.join(name for name, present in enrollment_parameters_state if not present)
            logger.error(
                '[Manual Order Creation Failure] Missing required enrollment data. Message: %s', missing_params
            )
            raise ValidationError('Missing required enrollment data: {}'.format(missing_params))

        return lms_user_id, learner_username, learner_email, course_run_key

    def _get_learner_user(self, lms_user_id, learner_username, learner_email):
        """
        Return the ecommerce user with username set to `learner_username` and email set to `learner_email`.

        If user exists then email will be upated to matach the `learner_email`.
        If user does not exist then a new one will be created.
        """
        learner_user, __ = get_user_model().objects.update_or_create(username=learner_username, defaults={
            'email': learner_email,
            'lms_user_id': lms_user_id
        })

        return learner_user

    def _get_or_create_discount_offer(self):
        """
        Get or Create 100% discount offer for `Manual Enrollemnt Order`.
        """
        condition, __ = Condition.objects.get_or_create(proxy_class=class_path(ManualEnrollmentOrderDiscountCondition))

        benefit, _ = Benefit.objects.get_or_create(
            proxy_class=class_path(ManualEnrollmentOrderDiscountBenefit),
            value=100,
            max_affected_items=1,
        )

        offer_kwargs = {
            'offer_type': ConditionalOffer.USER,
            'condition': condition,
            'benefit': benefit,
            'priority': OFFER_PRIORITY_MANUAL_ORDER,
        }

        offer, __ = ConditionalOffer.objects.get_or_create(
            name='Manual Course Enrollment Order Offer',
            defaults=offer_kwargs
        )

        return offer

    def handle_successful_order(self, order, request=None):  # pylint: disable=arguments-differ
        """
        Fulfill the order immediately.
        """
        for line in order.lines.all():
            line.set_status(LINE.COMPLETE)

        order.set_status(ORDER.COMPLETE)

        audit_log(
            'manual_order_fulfilled',
            amount=order.total_excl_tax,
            basket_id=order.basket.id,
            currency=order.currency,
            order_number=order.number,
            user_id=order.user.id,
            contains_coupon=order.contains_coupon
        )

        return order
