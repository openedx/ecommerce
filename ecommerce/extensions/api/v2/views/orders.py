"""HTTP endpoints for interacting with orders."""


import logging
from decimal import Decimal

import dateutil
import django_filters
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.decorators import method_decorator
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from oscar.core.loading import get_class, get_model
from requests.exceptions import ConnectionError  # pylint: disable=redefined-builtin
from requests.exceptions import HTTPError, RequestException, Timeout
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import DjangoModelPermissions, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from ecommerce.courses.models import Course
from ecommerce.courses.utils import get_course_run_detail
from ecommerce.enterprise.mixins import EnterpriseDiscountMixin
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
Product = get_model('catalogue', 'Product')
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
    filter_backends = (django_filters.rest_framework.DjangoFilterBackend,)
    filterset_class = OrderFilter

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

    @action(detail=True, methods=['put', 'patch'])
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


class ManualCourseEnrollmentOrderViewSet(EdxOrderPlacementMixin, EnterpriseDiscountMixin, ViewSet):
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
            >>>             "course_run_key": "course-v1:TestX+Test100+2019_T1",
            >>>             "discount_percentage": 75.0,
            >>>             "date_placed": '2020-02-11T09:38:47.634561+00:00',  # optional param, only for old records.
            >>>             "sales_force_id": '252F0060L00000ppWfu',
            >>>             "salesforce_opportunity_line_item": 'abcF0060L00000ppWfu',
            >>>             "mode": 'verified',
            >>>             "enterprise_customer_name": "an-enterprise-customer",
            >>>             "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
            >>>         },
            >>>         {
            >>>             "lms_user_id": 123,
            >>>             "username": "metoo",
            >>>             "email": "metoo@example.com",
            >>>             "course_run_key": "",
            >>>             "mode": 'professional',
            >>>             "enterprise_customer_name": "an-enterprise-customer",
            >>>             "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
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
            >>>             "discount_percentage": 75.0,
            >>>             "date_placed": '2020-02-11T09:38:47.634561+00:00',
            >>>             "sales_force_id": '252F0060L00000ppWfu',
            >>>             "salesforce_opportunity_line_item": 'abcF0060L00000ppWfu',
            >>>             "mode": 'verified',
            >>>             "enterprise_customer_name": "an-enterprise-customer",
            >>>             "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
            >>>             "status": "success",
            >>>             "detail": "EDX-123456",
            >>>             "new_order_created": True,
            >>>         },
            >>>         {
            >>>             "lms_user_id": 123,
            >>>             "username": "metoo",
            >>>             "email": "metoo@example.com",
            >>>             "course_run_key": "",
            >>>             "mode": 'professional',
            >>>             "enterprise_customer_name": "an-enterprise-customer",
            >>>             "enterprise_customer_uuid": "394a5ce5-6ff4-4b2b-bea1-a273c6920ae1",
            >>>             "status": "failure",
            >>>             "detail": "Missing required enrollmment data: `course_run_key`",
            >>>             "new_order_created": None,
            >>>         },
            >>>     ]
            >>> }
    """

    authentication_classes = (JwtAuthentication,)
    permission_classes = (IsAuthenticated, IsAdminUser)
    http_method_names = ['post']

    SUCCESS, FAILURE = "success", "failure"

    @staticmethod
    def existing_purchased_line(seat_product, user, site):
        """ Returns existing OrderLine object purchased by user whether in the form of course entitlement
        or course enrollment."""
        course_uuid = get_course_run_detail(site, seat_product.course.id)['course_uuid']
        products = Product.objects.filter(
            Q(pk=seat_product.pk) | Q(attributes__code='UUID', attribute_values__value_text=course_uuid)
        )
        return OrderLine.objects.filter(product__in=products, order__user=user, status=LINE.COMPLETE).first()

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
                    "course_run_key": <string>,
                    "discount_percentage": <float>,
                    "sales_force_id": <string>,
                    "salesforce_opportunity_line_item": <string>,
                    "mode": <string>,
                    "enterprise_customer_name": <string>,
                    "enterprise_customer_uuid": <string>,
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
                mode,
                discount_percentage,
                sales_force_id,
                salesforce_opportunity_line_item,
            ) = self._get_enrollment_data(enrollment)
        except ValidationError as ex:
            return dict(enrollment, status=self.FAILURE, detail=ex.message, new_order_created=None)

        logger.info(
            '[Manual Order Creation] Request received. User: %s, Email: %s, Course: %s, RequestUser: %s, '
            'Discount Percentage: %s, Salesforce Opportunity Id: %s, Salesforce Opportunity Line Item Id: %s',
            learner_username,
            learner_email,
            course_run_key,
            request_user.username,
            discount_percentage,
            sales_force_id,
            salesforce_opportunity_line_item,
        )

        learner_user = self._get_learner_user(lms_user_id, learner_username, learner_email)

        try:
            course = Course.objects.get(id=course_run_key)
        except Course.DoesNotExist:
            return dict(enrollment, status=self.FAILURE, detail="Course not found", new_order_created=None)

        seat_product = course.seat_products.filter(
            attributes__name='certificate_type',
            attribute_values__value_text=mode
        ).first()

        # check if an order already exists with the requested data
        try:
            order_line = self.existing_purchased_line(seat_product, learner_user, request_site)
        except (RequestException, ConnectionError, Timeout, HTTPError, AttributeError) as ex:
            logger.exception(
                "Could not access existing purchased line. User: %s, Site: %s, course_run_key: %s, message: %s",
                learner_user,
                request_site,
                course_run_key,
                ex,
            )
            return dict(enrollment, status=self.FAILURE, detail="Failed to create free order", new_order_created=None)
        if order_line:
            order = order_line.order
            self._update_all_orderline_with_enterprise_discount(order, discount_percentage)
            return dict(
                enrollment,
                status=self.SUCCESS,
                detail=order.number,
                new_order_created=False
            )

        basket = Basket.create_basket(request_site, learner_user)
        basket.add_product(seat_product)

        enterprise_customer_name = enrollment.get('enterprise_customer_name')
        enterprise_customer_uuid = enrollment.get('enterprise_customer_uuid')
        discount_offer = self._get_or_create_discount_offer(
            enterprise_customer_name,
            enterprise_customer_uuid,
            sales_force_id,
            salesforce_opportunity_line_item
        )
        Applicator().apply_offers(basket, [discount_offer])
        try:
            order = self.place_free_order(basket)
            self._update_order_according_to_date_place(order, enrollment.get('date_placed'))
            self._update_all_orderline_with_enterprise_discount(order, discount_percentage)
        except:  # pylint: disable=bare-except
            logger.exception(
                '[Manual Order Creation Failure] Failed to place the order. User: %s, Course: %s, Basket: %s, '
                'Product: %s',
                learner_user.username,
                course.id,
                basket.id,
                seat_product.id,
            )
            return dict(enrollment, status=self.FAILURE, detail="Failed to create free order", new_order_created=None)

        logger.info(
            '[Manual Order Creation] Order completed. User: %s, Course: %s, Basket: %s, Order: %s, Product: %s',
            learner_user.username,
            course.id,
            basket.id,
            seat_product.id,
            order.number,
        )
        return dict(enrollment, status=self.SUCCESS, detail=order.number, new_order_created=True)

    def _update_all_orderline_with_enterprise_discount(self, order, discount_percentage):
        """
        Updates all order's lines with calculated discount metrics if applicable
        """
        if discount_percentage is None:
            return

        # update_orderline_with_enterprise_discount function expects Decimal object
        discount_percentage = Decimal(discount_percentage)
        for line in order.lines.all():
            self.update_orderline_with_enterprise_discount_metadata(
                order,
                line,
                discount_percentage=discount_percentage,
                is_manual_order=True
            )

    def _update_order_according_to_date_place(self, order, date_placed):
        """
            This is a Single Time use functionality to created order records for old enrollments.
            We will revert this PR after using it.
        Args:
            order: An Order object
            date_placed: iso format datetime

        Returns:
            Nothing

        """
        if not date_placed:
            return

        date_placed = dateutil.parser.isoparse(date_placed)
        order.date_placed = date_placed
        order.save()

        for line in order.lines.all():
            old_stock = line.stockrecord.history.filter(history_date__lt=date_placed).order_by('-history_date').first()
            stock_record = old_stock or line.stockrecord
            price = stock_record.price_excl_tax or Decimal('0')
            quantity = line.quantity
            line.line_price_before_discounts_incl_tax = price * quantity
            line.line_price_before_discounts_excl_tax = price * quantity
            line.unit_price_incl_tax = price
            line.unit_price_excl_tax = price
            line.save()

        logger.info('[Manual Order Back populate] Order completed. Order: %s', order.number,)

    def _get_enrollment_data(self, enrollment):
        """
        Return parameters from incoming enrollment.

        Required Parameters:
            lms_user_id:  User's platform id.
            learner_username:  User's username.
            learner_email:  User's email.
            course_run_key:  Course key.
            mode: Course mode.

        Optional Parameters:
            discount_percentage: Discounted percentage for manual enrollment.
            sales_force_id: Salesforce opportunity id.
            salesforce_opportunity_line_item: Salesforce opportunity line item id.

        Raises:
            ValidationError: If any required parameter is not present in enrollment.
        """
        paid_modes = ['verified', 'professional']
        lms_user_id = enrollment.get('lms_user_id')
        learner_username = enrollment.get('username')
        learner_email = enrollment.get('email')
        course_run_key = enrollment.get('course_run_key')
        discount_percentage = enrollment.get('discount_percentage')
        sales_force_id = enrollment.get('sales_force_id')
        salesforce_opportunity_line_item = enrollment.get('salesforce_opportunity_line_item')
        mode = enrollment.get('mode')
        if not (lms_user_id and learner_username and learner_email and course_run_key and mode):
            enrollment_parameters_state = [
                ("'lms_user_id'", bool(lms_user_id)),
                ("'username'", bool(learner_username)),
                ("'email'", bool(learner_email)),
                ("'course_run_key'", bool(course_run_key)),
                ("'mode'", bool(mode)),
            ]
            missing_params = ', '.join(name for name, present in enrollment_parameters_state if not present)
            logger.error(
                '[Manual Order Creation Failure] Missing required enrollment data. Message: %s', missing_params
            )
            raise ValidationError('Missing required enrollment data: {}'.format(missing_params))

        if mode not in paid_modes:
            raise ValidationError('Course mode should be paid')

        if discount_percentage is not None:
            if not isinstance(discount_percentage, float) or (discount_percentage < 0.0 or discount_percentage > 100.0):
                raise ValidationError('Discount percentage should be a float from 0 to 100.')
        return lms_user_id, learner_username, learner_email, course_run_key, mode, discount_percentage,\
            sales_force_id, salesforce_opportunity_line_item

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

    def _get_or_create_discount_offer(
            self, enterprise_customer_name, enterprise_customer_uuid, sales_force_id, salesforce_opportunity_line_item):
        """
        Get or Create 100% discount offer for `Manual Enrollment Order`.
        """
        condition, _ = Condition.objects.get_or_create(
            proxy_class=class_path(ManualEnrollmentOrderDiscountCondition),
            enterprise_customer_uuid=enterprise_customer_uuid
        )

        if condition.enterprise_customer_name != enterprise_customer_name:
            condition.enterprise_customer_name = enterprise_customer_name
            condition.save()

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
            name='Manual Course Enrollment Order Offer for enterprise {}'.format(enterprise_customer_uuid),
            defaults=offer_kwargs
        )
        if sales_force_id and offer.sales_force_id != sales_force_id:
            offer.sales_force_id = sales_force_id
            offer.save()

        if salesforce_opportunity_line_item and\
                offer.salesforce_opportunity_line_item != salesforce_opportunity_line_item:
            offer.salesforce_opportunity_line_item = salesforce_opportunity_line_item
            offer.save()

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
