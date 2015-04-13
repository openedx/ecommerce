"""HTTP endpoints for interacting with Oscar."""
import logging

from django.conf import settings
from django.http import Http404
from oscar.core.loading import get_class, get_classes, get_model
from rest_framework import status
from rest_framework.generics import UpdateAPIView, RetrieveAPIView, ListCreateAPIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from ecommerce.extensions.api import data, exceptions, serializers
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.fulfillment.mixins import FulfillmentMixin
from ecommerce.extensions.payment.helpers import get_processor_class


logger = logging.getLogger(__name__)

Free = get_class('shipping.methods', 'Free')
EventHandler = get_class('order.processing', 'EventHandler')
Order = get_model('order', 'Order')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')

# pylint: disable=unbalanced-tuple-unpacking
OrderCreator, OrderNumberGenerator = get_classes('order.utils', ['OrderCreator', 'OrderNumberGenerator'])


class RetrieveOrderView(RetrieveAPIView):
    """Allow the viewing of Paid Orders.

    Given an order number, allow the viewing of a paid order. This endpoint will only return an order if
    it in a PAID state, or is in a preceding state in the order workflow (COMPLETE, FULFILLMENT_ERROR, REFUNDED).
    This endpoint will return a 404 response status if no order is found, or if an order is found that is still
    pending payment.  This endpoint will only return orders associated with the authenticated user.

    Returns:
        Order: The requested order.

    Example:
        >>> url = 'http://localhost:8002/api/v1/orders/100022'
        >>> headers = {
            'content-type': 'application/json',
            'Authorization': 'JWT ' + token
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
            "number": "100022",
            "status": "Complete",
            "total_excl_tax": 0.0
        }'
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrderSerializer
    lookup_field = 'number'
    queryset = Order.objects.all()

    def get_object(self):
        """Retrieve the order for this request.

        Retrieves the associated order, and if it is paid and associated with the request user, returns it. Otherwise,
        raises an Http404 exception.

        Returns:
            Order: The associated order.

        Raises:
            Http404: Returns a 404 not found exception if the request order cannot be found, the order is not paid, or
                is not associated with the request user.

        """
        order = super(RetrieveOrderView, self).get_object()
        if order and order.is_paid and order.user.username == self.request.user.username:
            return order
        else:
            raise Http404


class OrderListCreateAPIView(FulfillmentMixin, ListCreateAPIView):
    """
    Endpoint for listing or creating orders.

    When listing orders, results are ordered with the newest order being the first in the list of results.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrderSerializer

    FREE = 0

    def get_queryset(self):
        return self.request.user.orders.order_by('-date_placed')

    def create(self, request, *args, **kwargs):
        """Add one product to a basket, then prepare an order.

        Protected by JWT authentication. Consuming services (e.g., the LMS)
        must authenticate themselves by passing a JWT in the Authorization
        HTTP header, prepended with the string 'JWT'. The JWT payload should
        contain user details. At a minimum, these details must include a
        username; providing an email is recommended.

        Expects a SKU to be provided in the POST data, which is then used
        to populate the user's basket with the corresponding product, freeze
        that basket, and prepare an order using that basket. If the order
        total is zero (i.e., the ordered product was free), an attempt to
        fulfill the order is made.

        Arguments:
            request (HttpRequest)

        Returns:
            HTTP_200_OK if the order was created successfully, with order data in JSON format
            HTTP_400_BAD_REQUEST if the client has provided invalid data or has attempted
                to add an unavailable product to their basket, with reason for the failure
                in JSON format
            HTTP_401_UNAUTHORIZED if an unauthenticated request is denied permission to access
                the endpoint
            HTTP_429_TOO_MANY_REQUESTS if the client has made requests at a rate exceeding that
                allowed by the OrdersThrottle

        Example:
            Create an order for the user with username 'Saul' as follows. (Successful fulfillment
            requires that a user with username 'Saul' exists on the LMS, and that EDX_API_KEY be
            configured on both Oscar and the LMS.)

            >>> url = 'http://localhost:8002/api/v1/orders/'
            >>> data = {'sku': 'SEAT-HONOR-EDX-DEMOX-DEMO-COURSE'}
            >>> token = jwt.encode({'username': 'Saul', 'email': 'saul@bettercallsaul.com'}, 'insecure-secret-key')
            >>> headers = {
                'content-type': 'application/json',
                'Authorization': 'JWT ' + token
            }
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
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
                "number": "OSCR-100021",
                "status": "Complete",
                "total_excl_tax": 0.0
            }'
        """
        sku = request.data.get('sku')
        if sku:
            try:
                product = data.get_product(sku)
            except exceptions.ProductNotFoundError as error:
                return self._report_bad_request(error.message, exceptions.PRODUCT_NOT_FOUND_USER_MESSAGE)
        else:
            return self._report_bad_request(
                exceptions.SKU_NOT_FOUND_DEVELOPER_MESSAGE,
                exceptions.SKU_NOT_FOUND_USER_MESSAGE
            )

        basket = data.get_basket(request.user)
        availability = basket.strategy.fetch_for_product(product).availability

        # If an exception is raised before order creation but after basket creation,
        # an empty basket for the user will be left in the system. However, if this
        # user attempts to order again, the `get_basket` utility will merge all old
        # baskets with a new one, returning a fresh basket.
        if not availability.is_available_to_buy:
            return self._report_bad_request(
                exceptions.PRODUCT_UNAVAILABLE_DEVELOPER_MESSAGE.format(
                    sku=sku,
                    availability=availability.message
                ),
                exceptions.PRODUCT_UNAVAILABLE_USER_MESSAGE
            )

        payment_processor = get_processor_class(settings.PAYMENT_PROCESSORS[0])

        order = self._prepare_order(basket, product, sku, payment_processor)
        if order.status == ORDER.PAID:
            logger.info(
                u"Attempting to immediately fulfill order [%s] totaling [%.2f %s]",
                order.number,
                order.total_excl_tax,
                order.currency,
            )

            order = self.fulfill_order(order)

        order_data = self._assemble_order_data(order, payment_processor)

        return Response(order_data, status=status.HTTP_200_OK)

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

    def _prepare_order(self, basket, product, sku, payment_processor):
        """Prepare an order consisting of a single product for a user."""
        # Baskets with a status of 'Frozen' or 'Submitted' are not retrieved at the
        # start of a new order. To prevent stale items from ending up in the basket
        # at the start of an order, we want to guarantee that this endpoint creates
        # new orders iff the basket in use is frozen first. Since ATOMIC_REQUESTS is
        # assumed to be enabled, wrapping this block with an `atomic()` context
        # manager to ensure atomicity would be redundant.
        basket.add_product(product)
        basket.freeze()

        logger.info(
            u"Added product [SKU: %s] to basket [%d]",
            sku,
            basket.id,
        )

        shipping_method = Free()
        shipping_charge = shipping_method.calculate(basket)
        total = OrderTotalCalculator().calculate(basket, shipping_charge)

        order = OrderCreator().place_order(
            basket,
            total,
            shipping_method,
            shipping_charge,
            user=basket.owner,
            order_number=OrderNumberGenerator.order_number(basket),
            status=ORDER.OPEN
        )

        logger.info(
            u"Created order [%s] totaling [%.2f %s] using basket [%d]; payment to be processed by [%s]",
            order.number,
            order.total_excl_tax,
            order.currency,
            basket.id,
            payment_processor.NAME
        )

        # Update the order to BEING_PROCESSED for all orders
        order.set_status(ORDER.BEING_PROCESSED)

        # If the product constituting the order is free, we mark the order
        # as paid (as dictated by the order status pipeline) so that the
        # fulfillment API will agree to fulfill it.
        if order.total_excl_tax == self.FREE:
            order.set_status(ORDER.PAID)
            logger.info(u"Marked order [%s] as [%s]", order.number, ORDER.PAID)

        # Mark the basket as submitted
        basket.submit()

        return order

    def _assemble_order_data(self, order, payment_processor):
        """Assemble a dictionary of metadata for the provided order."""
        order_data = serializers.OrderSerializer(order).data
        order_data['payment_parameters'] = payment_processor().get_transaction_parameters(order)

        return order_data


class OrderFulfillView(FulfillmentMixin, UpdateAPIView):
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
