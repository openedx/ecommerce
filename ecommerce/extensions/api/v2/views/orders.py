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

            API to
            * create an order for learners manually enrolled in to a course but
              they have paid the course price outside of the ecommerce.
            * mark an existing `completed` order as failed.

        **Behavior**

            Implements POST and PUT actions.

            POST /api/v2/manual_course_enrollment_order/
            >>> {
            >>>     "lms_user_id": 111,
            >>>     "username": "me",
            >>>     "email": "me@example.com",
            >>>     "course_run_key": "course-v1:TestX+Test100+2019_T1"
            >>> }

            Success Response
            >>> {
            >>>     "id": 13,
            >>>     "order_number": "EDX-100189"
            >>> }

            PUT /api/v2/manual_course_enrollment_order/13/fail
            >>> {
            >>>     "reason": "Course Enrollment Failed"
            >>> }

            Success Response
            >>> {
            >>>     "id": 13,
            >>>     "order_number": "EDX-100189"
            >>> }
    """

    authentication_classes = (JwtAuthentication,)
    permission_classes = (IsAuthenticated, IsAdminUser)
    http_method_names = ['post', 'put']

    @detail_route(methods=['put'])
    def fail(self, request, pk):
        """
        PUT /api/v2/manual_course_enrollment_order/13/fail

        Requires a JSON object of the following format:
        >>> {
        >>>     "reason": "Enrollment Failed"
        >>> }

        Request Body:
        *reason*
            Reason for the failure of order.
        """
        reason = request.data.get('reason')

        logger.info(
            '[Manual Order Update] Request received. RequestUser: %s, OrderId: %s, Reason: %s',
            request.user.username, pk, reason
        )

        if not reason:
            return Response({'detail': 'Incorrect reason for order update'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # only update the `completed` order, dosen't make sense to fail a non-completed order
            order = Order.objects.get(pk=pk, status=ORDER.COMPLETE)
        except Order.DoesNotExist:
            return Response(
                {'detail': 'Either order does not exist or order is not completed'},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.notes.create(message=reason, note_type='Error')

        # setting the `line` and order status forcefully instad of using `set_status` because
        # oscar does not allow to change the status of completed `order` or `line`
        for line in order.lines.all():
            line.status = LINE.FULFILLMENT_SERVER_ERROR
            line.save()

        order.status = ORDER.FULFILLMENT_ERROR
        order.save()

        return Response(
            {
                'id': order.id,
                'order_number': order.number,
            },
            status=status.HTTP_200_OK
        )

    def create(self, request):
        """
        POST /api/v2/manual_course_enrollment_order/

        Requires a JSON object of the following format:
        >>> {
        >>>     "lms_user_id": 111,
        >>>     "username": "me",
        >>>     "email": "me@example.com",
        >>>     "course_run_key": "course-v1:TestX+Test100+2019_T1"
        >>> }

        Request Body:
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
            lms_user_id, learner_username, learner_email, course_run_key = self._get_required_request_data(request)
        except ValidationError as ex:
            return Response({'detail': ex.message}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(
            '[Manual Order Creation] Request received. User: %s, Email: %s, Course: %s, RequestUser: %s',
            learner_username,
            learner_email,
            course_run_key,
            request.user.username,
        )

        learner_user = self._get_learner_user(lms_user_id, learner_username, learner_email)

        try:
            course = Course.objects.get(id=course_run_key)
        except Course.DoesNotExist:
            return Response({'detail': 'course not found'}, status=status.HTTP_400_BAD_REQUEST)

        seat_product = course.seat_products.filter(
            attributes__name='certificate_type'
        ).exclude(
            attribute_values__value_text='audit'
        ).first()

        # check if an order already exists with the requested data
        order_line = OrderLine.objects.filter(product=seat_product, order__user=learner_user, status=LINE.COMPLETE)
        if order_line.exists():
            order = Order.objects.get(id=order_line.first().order_id)
            return Response(
                {
                    'id': order.id,
                    'order_number': order.number,
                    'detail': 'Order already exists'
                },
                status=status.HTTP_200_OK
            )

        basket = Basket.create_basket(request.site, learner_user)
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
            return Response({'detail': 'Failed to create free order'}, status=status.HTTP_400_BAD_REQUEST)

        logger.info(
            '[Manual Order Creation] Order completed. User: %s, Course: %s, Basket: %s, Order: %s, Product: %s',
            learner_user.username,
            course.id,
            basket.id,
            seat_product.id,
            order.number,
        )

        response = {
            'id': order.id,
            'order_number': order.number,
        }
        return Response(response, status=status.HTTP_201_CREATED)

    def _get_required_request_data(self, request):
        """
        Return required parameters from incoming request.

        Raises:
            ValidationError: If any required parameter is not present in request.
        """
        lms_user_id = request.data.get('lms_user_id')
        learner_username = request.data.get('username')
        learner_email = request.data.get('email')
        course_run_key = request.data.get('course_run_key')
        if not (lms_user_id and learner_username and learner_email and course_run_key):
            request_parameters_state = [
                ("'lms_user_id'", bool(lms_user_id)),
                ("'username'", bool(learner_username)),
                ("'email'", bool(learner_email)),
                ("'course_run_key'", bool(course_run_key)),
            ]
            missing_params = ', '.join(name for name, present in request_parameters_state if not present)
            logger.error(
                '[Manual Order Creation Failure] Missing required request data. Message: %s', missing_params
            )
            raise ValidationError('Missing required request data: {}'.format(missing_params))

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
