"""HTTP endpoints for interacting with Oscar."""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from oscar.core.loading import get_model
from rest_framework import status, generics, viewsets, mixins
from rest_framework.decorators import detail_route
from rest_framework.exceptions import ParseError
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions, IsAdminUser
from rest_framework.response import Response
from rest_framework_extensions.mixins import NestedViewSetMixin
import waffle

from ecommerce.core.constants import COURSE_ID_REGEX
from ecommerce.courses.models import Course
from ecommerce.extensions.analytics.utils import audit_log
from ecommerce.extensions.api import data as data_api, exceptions as api_exceptions, serializers
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.exceptions import BadRequestException
from ecommerce.extensions.api.permissions import CanActForUser
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.fulfillment.mixins import FulfillmentMixin
from ecommerce.extensions.payment import exceptions as payment_exceptions
from ecommerce.extensions.payment.helpers import (get_processor_class, get_default_processor_class,
                                                  get_processor_class_by_name)
from ecommerce.extensions.refund.api import find_orders_associated_with_course, create_refunds


logger = logging.getLogger(__name__)

Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
Refund = get_model('refund', 'Refund')
User = get_user_model()


class BasketCreateView(EdxOrderPlacementMixin, generics.CreateAPIView):
    """Endpoint for creating baskets.

    If requested, performs checkout operations on baskets, placing an order if
    the contents of the basket are free, and generating payment parameters otherwise.
    """
    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        """Add products to the authenticated user's basket.

        Expects an array of product objects, 'products', each containing a SKU, in the request
        body. The SKUs are used to populate the user's basket with the corresponding products.

        The caller indicates whether checkout should occur by providing a Boolean value
        in the request body, 'checkout'. If checkout operations are requested and the
        contents of the user's basket are free, an order is placed immediately.

        If checkout operations are requested but the contents of the user's basket are not
        free, pre-payment operations are performed instead of placing an order. The caller
        indicates which payment processor to use by providing a string in the request body,
        'payment_processor_name'.

        Protected by JWT authentication. Consuming services (e.g., the LMS)
        must authenticate themselves by passing a JWT in the Authorization
        HTTP header, prepended with the string 'JWT '. The JWT payload should
        contain user details. At a minimum, these details must include a
        username; providing an email is recommended.

        Arguments:
            request (HttpRequest): With parameters 'products', 'checkout', and
                'payment_processor_name' in the body.

        Returns:
            200 if a basket was created successfully; the basket ID is included in the response body along with
                either an order number corresponding to the placed order (None if one wasn't placed) or
                payment information (None if payment isn't required).
            400 if the client provided invalid data or attempted to add an unavailable product to their basket,
                with reason for the failure in JSON format.
            401 if an unauthenticated request is denied permission to access the endpoint.
            429 if the client has made requests at a rate exceeding that allowed by the configured rate limit.
            500 if an error occurs when attempting to initiate checkout.

        Examples:
            Create a basket for the user with username 'Saul' as follows. Successful fulfillment
            requires that a user with username 'Saul' exists on the LMS, and that EDX_API_KEY be
            configured within both the LMS and the ecommerce service.

            >>> url = 'http://localhost:8002/api/v2/baskets/'
            >>> token = jwt.encode({'username': 'Saul', 'email': 'saul@bettercallsaul.com'}, 'insecure-secret-key')
            >>> headers = {
                'content-type': 'application/json',
                'Authorization': 'JWT ' + token
            }

            If checkout is not desired:

            >>> data = {'products': [{'sku': 'SOME-SEAT'}, {'sku': 'SOME-OTHER-SEAT'}], 'checkout': False}
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> response.json()
            {
                u'id': 7,
                u'order': None,
                u'payment_data': None
            }

            If the product with SKU 'FREE-SEAT' is free and checkout is desired:

            >>> data = {'products': [{'sku': 'FREE-SEAT'}], 'checkout': True, 'payment_processor_name': 'paypal'}
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> response.json()
            {
                u'id': 7,
                u'order': {u'number': u'OSCR-100007'},
                u'payment_data': None
            }

            If the product with SKU 'PAID-SEAT' is not free and checkout is desired:

            >>> data = {'products': [{'sku': 'PAID-SEAT'}], 'checkout': True, 'payment_processor_name': 'paypal'}
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> response.json()
            {
                u'id': 7,
                u'order': None,
                u'payment_data': {
                    u'payment_processor_name': u'paypal',
                    u'payment_form_data': {...},
                    u'payment_page_url': u'https://www.someexternallyhostedpaymentpage.com'
                }
            }
        """
        basket = data_api.get_basket(request.user)

        requested_products = request.data.get(AC.KEYS.PRODUCTS)
        if requested_products:
            for requested_product in requested_products:
                # Ensure the requested products exist
                sku = requested_product.get(AC.KEYS.SKU)
                if sku:
                    try:
                        product = data_api.get_product(sku)
                    except api_exceptions.ProductNotFoundError as error:
                        return self._report_bad_request(error.message, api_exceptions.PRODUCT_NOT_FOUND_USER_MESSAGE)
                else:
                    return self._report_bad_request(
                        api_exceptions.SKU_NOT_FOUND_DEVELOPER_MESSAGE,
                        api_exceptions.SKU_NOT_FOUND_USER_MESSAGE
                    )

                # Ensure the requested products are available for purchase before adding them to the basket
                availability = basket.strategy.fetch_for_product(product).availability
                if not availability.is_available_to_buy:
                    return self._report_bad_request(
                        api_exceptions.PRODUCT_UNAVAILABLE_DEVELOPER_MESSAGE.format(
                            sku=sku,
                            availability=availability.message
                        ),
                        api_exceptions.PRODUCT_UNAVAILABLE_USER_MESSAGE
                    )

                basket.add_product(product)
                logger.info(u"Added product with SKU [%s] to basket [%d]", sku, basket.id)
        else:
            # If no products were included in the request, we cannot checkout.
            return self._report_bad_request(
                api_exceptions.PRODUCT_OBJECTS_MISSING_DEVELOPER_MESSAGE,
                api_exceptions.PRODUCT_OBJECTS_MISSING_USER_MESSAGE
            )

        if request.data.get(AC.KEYS.CHECKOUT) is True:
            # Begin the checkout process, if requested, with the requested payment processor.
            payment_processor_name = request.data.get(AC.KEYS.PAYMENT_PROCESSOR_NAME)
            if payment_processor_name:
                try:
                    payment_processor = get_processor_class_by_name(payment_processor_name)
                except payment_exceptions.ProcessorNotFoundError as error:
                    return self._report_bad_request(
                        error.message,
                        payment_exceptions.PROCESSOR_NOT_FOUND_USER_MESSAGE
                    )
            else:
                payment_processor = get_default_processor_class()

            try:
                response_data = self._checkout(basket, payment_processor())
            except Exception as ex:  # pylint: disable=broad-except
                basket.thaw()
                logger.exception('Failed to initiate checkout for Basket [%d]. Basket has been thawed.', basket.id)
                return Response({'developer_message': ex.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Return a serialized basket, if checkout was not requested.
            response_data = self._generate_basic_response(basket)

        return Response(response_data, status=status.HTTP_200_OK)

    def _checkout(self, basket, payment_processor):
        """Perform checkout operations for the given basket.

        If the contents of the basket are free, places an order immediately. Otherwise,
        performs any operations necessary to prepare for payment.

        To prevent stale items from ending up in a basket at checkout, baskets should
        always be frozen during checkout. Baskets with a status of 'Frozen' or 'Submitted'
        are not retrieved when fetching a basket for the user.

        Arguments:
            basket (Basket): The basket on which to perform checkout operations.
            payment_processor (class): An instance of the payment processor class corresponding
                to the payment processor the user will visit to pay for the items in their basket.

        Returns:
            dict: Response data.
        """
        basket.freeze()

        audit_log(
            'basket_frozen',
            amount=basket.total_excl_tax,
            basket_id=basket.id,
            currency=basket.currency,
            user_id=basket.owner.id
        )

        response_data = self._generate_basic_response(basket)

        if basket.total_excl_tax == AC.FREE:
            order_metadata = data_api.get_order_metadata(basket)

            logger.info(
                u"Preparing to place order [%s] for the contents of basket [%d]",
                order_metadata[AC.KEYS.ORDER_NUMBER],
                basket.id,
            )

            # Place an order, attempting to fulfill it immediately
            order = self.handle_order_placement(
                order_number=order_metadata[AC.KEYS.ORDER_NUMBER],
                user=basket.owner,
                basket=basket,
                shipping_address=None,
                shipping_method=order_metadata[AC.KEYS.SHIPPING_METHOD],
                shipping_charge=order_metadata[AC.KEYS.SHIPPING_CHARGE],
                billing_address=None,
                order_total=order_metadata[AC.KEYS.ORDER_TOTAL],
            )

            # Note: Our order serializer could be used here, but in an effort to pare down the information
            # returned by this endpoint, simply returning the order number will suffice for now.
            response_data[AC.KEYS.ORDER] = {AC.KEYS.ORDER_NUMBER: order.number}
        else:
            parameters = payment_processor.get_transaction_parameters(basket, request=self.request)
            payment_page_url = parameters.pop('payment_page_url')

            response_data[AC.KEYS.PAYMENT_DATA] = {
                AC.KEYS.PAYMENT_PROCESSOR_NAME: payment_processor.NAME,
                AC.KEYS.PAYMENT_FORM_DATA: parameters,
                AC.KEYS.PAYMENT_PAGE_URL: payment_page_url,
            }

        return response_data

    def _generate_basic_response(self, basket):
        """Create a dictionary to be used as response data.

        The dictionary contains placeholders for order and payment information.

        Arguments:
            basket (Basket): The basket whose information should be included in the response data.

        Returns:
            dict: Basic response data.
        """
        # Note: A basket serializer could be used here, but in an effort to pare down the information
        # returned by this endpoint, simply returning the basket ID will suffice for now.
        response_data = {
            AC.KEYS.BASKET_ID: basket.id,
            AC.KEYS.ORDER: None,
            AC.KEYS.PAYMENT_DATA: None,
        }

        return response_data

    def _report_bad_request(self, developer_message, user_message):
        """Log error and create a response containing conventional error messaging."""
        logger.error(developer_message)
        return Response(
            {
                'developer_message': developer_message,
                'user_message': user_message
            },
            status=status.HTTP_400_BAD_REQUEST
        )


class OrderListView(generics.ListAPIView):
    """Endpoint for listing orders.

    Results are ordered with the newest order being the first in the list of results.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrderSerializer

    def get_queryset(self):
        user = self.request.user
        qs = user.orders

        if user.is_superuser:
            qs = Order.objects.all()

        return qs.order_by('-date_placed')


class OrderRetrieveView(generics.RetrieveAPIView):
    """Allow the viewing of orders.

    Given an order number, allow the viewing of the corresponding order. This endpoint will return a 404 response
    status if no order is found. This endpoint will only return orders associated with the authenticated user.

    Returns:
        Order: The requested order.

    Example:
        >>> url = 'http://localhost:8002/api/v2/orders/100022'
        >>> headers = {
            'content-type': 'application/json',
            'Authorization': 'JWT '  token
        }
        >>> response = requests.get(url, headers=headers)
        >>> response.status_code
        200
        >>> response.content
        '{
            "currency": "USD",
            "date_placed": "2015-02-27T18:42:34.017218Z",
            "lines": [
                {
                    "description": "Seat in DemoX Course with Honor Certificate",
                    "status": "Complete",
                    "title": "Seat in DemoX Course with Honor Certificate",
                    "unit_price_excl_tax": 0.0
                }
            ],
            "number": "OSCR-100022",
            "status": "Complete",
            "total_excl_tax": 0.0
        }'
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrderSerializer
    lookup_field = AC.KEYS.ORDER_NUMBER

    def get_queryset(self):
        """
        Returns a queryset consisting of only the authenticated user's orders.

        This ensures we do not allow one user to view the data of another user.
        """
        return self.request.user.orders


class OrderByBasketRetrieveView(OrderRetrieveView):
    """Allow the viewing of Orders by Basket.

    Works exactly the same as OrderRetrieveView, except that orders are looked
    up via the id of the related basket.
    """
    lookup_field = 'basket_id'


class OrderFulfillView(FulfillmentMixin, generics.UpdateAPIView):
    permission_classes = (IsAuthenticated, DjangoModelPermissions,)
    lookup_field = 'number'
    queryset = Order.objects.all()
    serializer_class = serializers.OrderSerializer

    def update(self, request, *args, **kwargs):
        order = self.get_object()

        if not order.can_retry_fulfillment:
            return Response(status=status.HTTP_406_NOT_ACCEPTABLE)

        logger.info('Retrying fulfillment of order [%s]...', order.number)
        order = self.fulfill_order(order)

        if order.can_retry_fulfillment:
            logger.warning('Fulfillment of order [%s] failed!', order.number)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = self.get_serializer(order)
        return Response(serializer.data)


class PaymentProcessorListView(generics.ListAPIView):
    """View that lists the available payment processors."""
    pagination_class = None
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.PaymentProcessorSerializer

    def get_queryset(self):
        """Fetch the list of payment processor classes based on Django settings."""
        return [get_processor_class(path) for path in settings.PAYMENT_PROCESSORS]


class RefundCreateView(generics.CreateAPIView):
    """
    Creates refunds.

    Given a username and course ID, this view finds and creates a refund for each order
    matching the following criteria:

        * Order was placed by the User linked to username.
        * Order is in the COMPLETE state.
        * Order has at least one line item associated with the course ID.

    Note that only the line items associated with the course ID will be refunded.
    Items associated with a different course ID, or not associated with any course ID, will NOT be refunded.

    With the exception of superusers, users may only create refunds for themselves.
    Attempts to create refunds for other users will fail with HTTP 403.

    If refunds are created, a list of the refund IDs will be returned along with HTTP 201.
    If no refunds are created, HTTP 200 will be returned.
    """
    permission_classes = (IsAuthenticated, CanActForUser)

    def create(self, request, *args, **kwargs):
        """ Creates refunds, if eligible orders exist. """
        course_id = request.data.get('course_id')
        username = request.data.get('username')

        if not course_id:
            raise BadRequestException('No course_id specified.')

        # We should always have a username value as long as CanActForUser is in place.
        if not username:  # pragma: no cover
            raise BadRequestException('No username specified.')

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise BadRequestException('User "{}" does not exist.'.format(username))

        refunds = []

        # We can only create refunds if the user has orders.
        if user.orders.exists():
            orders = find_orders_associated_with_course(user, course_id)
            refunds = create_refunds(orders, course_id)

        # Return HTTP 201 if we created refunds.
        if refunds:
            refund_ids = [refund.id for refund in refunds]
            return Response(refund_ids, status=status.HTTP_201_CREATED)

        # Return HTTP 200 if we did NOT create refunds.
        return Response([], status=status.HTTP_200_OK)


class RefundProcessView(generics.UpdateAPIView):
    """
    Process--approve or deny--refunds.

    This view can be used to approve, or deny, a Refund. Under normal conditions, the view returns HTTP status 200
    and a serialized Refund. In the event of an error, the view will still return a serialized Refund (to reflect any
    changed statuses); however, HTTP status will be 500.

    Only staff users are permitted to use this view.
    """
    permission_classes = (IsAuthenticated, IsAdminUser,)
    queryset = Refund.objects.all()
    serializer_class = serializers.RefundSerializer

    def update(self, request, *args, **kwargs):
        APPROVE = 'approve'
        DENY = 'deny'

        action = request.data.get('action', '').lower()

        if action not in (APPROVE, DENY):
            raise ParseError('The action [{}] is not valid.'.format(action))

        refund = self.get_object()
        result = False

        if action == APPROVE:
            result = refund.approve()
        elif action == DENY:
            result = refund.deny()

        http_status = status.HTTP_200_OK if result else status.HTTP_500_INTERNAL_SERVER_ERROR
        serializer = self.get_serializer(refund)
        return Response(serializer.data, status=http_status)


class NonDestroyableModelViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):
    pass


class CourseViewSet(NonDestroyableModelViewSet):
    lookup_value_regex = COURSE_ID_REGEX
    queryset = Course.objects.all()
    serializer_class = serializers.CourseSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get_serializer_context(self):
        context = super(CourseViewSet, self).get_serializer_context()
        context['include_products'] = bool(self.request.GET.get('include_products', False))
        return context

    @detail_route(methods=['post'])
    def publish(self, request, pk=None):  # pylint: disable=unused-argument
        """ Publish the course to LMS. """
        course = self.get_object()
        published = False
        msg = 'Course [{course_id}] was not published to LMS ' \
              'because the switch [publish_course_modes_to_lms] is disabled.'

        if waffle.switch_is_active('publish_course_modes_to_lms'):
            published = course.publish_to_lms()
            if published:
                msg = 'Course [{course_id}] was successfully published to LMS.'
            else:
                msg = 'An error occurred while publishing [{course_id}] to LMS.'

        return Response({'status': msg.format(course_id=course.id)},
                        status=status.HTTP_200_OK if published else status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductViewSet(NestedViewSetMixin, NonDestroyableModelViewSet):
    queryset = Product.objects.all()
    serializer_class = serializers.ProductSerializer
    permission_classes = (IsAuthenticated, IsAdminUser,)


class AtomicPublicationView(generics.CreateAPIView, generics.UpdateAPIView):
    """Attempt to save and publish a Course and associated products.

    If either fails, the entire operation is rolled back. This keeps Otto and the LMS in sync.
    """
    permission_classes = (IsAuthenticated, IsAdminUser,)
    serializer_class = serializers.AtomicPublicationSerializer

    def post(self, request, *args, **kwargs):
        return self._save_and_publish(request.data)

    def put(self, request, *args, **kwargs):
        return self._save_and_publish(request.data, course_id=kwargs['course_id'])

    def _save_and_publish(self, data, course_id=None):
        """Create or update a Course and associated products, then publish the result."""
        if course_id is not None:
            data['id'] = course_id

        serializer = self.get_serializer(data=data)
        is_valid = serializer.is_valid(raise_exception=True)
        if is_valid:
            created, failure, message = serializer.save()
            if failure:
                return Response({'error': message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                content = serializer.data
                content['message'] = message if message else None
                return Response(content, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
