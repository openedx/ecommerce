"""HTTP endpoints for interacting with Oscar."""
import logging

from django.conf import settings
from django.http import Http404
from oscar.core.loading import get_model
from rest_framework import status
from rest_framework.generics import CreateAPIView, RetrieveAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ecommerce.extensions.api import data, exceptions as api_exceptions, serializers
from ecommerce.extensions.api.constants import APIConstants as AC
# noinspection PyUnresolvedReferences
from ecommerce.extensions.api.v1.views import OrderFulfillView  # pylint: disable=unused-import
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment import exceptions as payment_exceptions
from ecommerce.extensions.payment.helpers import (get_processor_class, get_default_processor_class,
                                                  get_processor_class_by_name)


logger = logging.getLogger(__name__)

Order = get_model('order', 'Order')


class BasketCreateView(EdxOrderPlacementMixin, CreateAPIView):
    """Endpoint for creating baskets.

    If requested, performs checkout operations on baskets, placing an order if
    the contents of the basket are free, and generating payment parameters otherwise.
    """
    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        """Add products to the authenticated user's basket.

        Expects a list of product objects, 'products', each containing a SKU, in the request
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
            HTTP_200_OK if a basket was created successfully; the basket ID is included in
                the response body along with either an order number corresponding to the placed
                order (None if one wasn't placed) or payment information (None if payment isn't required).
            HTTP_400_BAD_REQUEST if the client provided invalid data or attempted to add an
                unavailable product to their basket, with reason for the failure in JSON format.
            HTTP_401_UNAUTHORIZED if an unauthenticated request is denied permission to access
                the endpoint.
            HTTP_429_TOO_MANY_REQUESTS if the client has made requests at a rate exceeding that
                allowed by the configured rate limit.

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
            >>> json.loads(response.content)
            {
                u'id': 7,
                u'order': None,
                u'payment_data': None
            }

            If the product with SKU 'FREE-SEAT' is free and checkout is desired:

            >>> data = {'products': [{'sku': 'FREE-SEAT'}], 'checkout': True, 'payment_processor_name': 'paypal'}
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> json.loads(response.content)
            {
                u'id': 7,
                u'order': {u'number': u'OSCR-100007'},
                u'payment_data': None
            }

            If the product with SKU 'PAID-SEAT' is not free and checkout is desired:

            >>> data = {'products': [{'sku': 'PAID-SEAT'}], 'checkout': True, 'payment_processor_name': 'paypal'}
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> json.loads(response.content)
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
        basket = data.get_basket(request.user)

        requested_products = request.data.get(AC.KEYS.PRODUCTS)
        if requested_products:
            for requested_product in requested_products:
                sku = requested_product.get(AC.KEYS.SKU)
                if sku:
                    try:
                        product = data.get_product(sku)
                    except api_exceptions.ProductNotFoundError as error:
                        return self._report_bad_request(error.message, api_exceptions.PRODUCT_NOT_FOUND_USER_MESSAGE)
                else:
                    return self._report_bad_request(
                        api_exceptions.SKU_NOT_FOUND_DEVELOPER_MESSAGE,
                        api_exceptions.SKU_NOT_FOUND_USER_MESSAGE
                    )

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
                logger.info(
                    u"Added product with SKU [%s] to basket [%d]",
                    sku,
                    basket.id,
                )
        else:
            return self._report_bad_request(
                api_exceptions.PRODUCT_OBJECTS_MISSING_DEVELOPER_MESSAGE,
                api_exceptions.PRODUCT_OBJECTS_MISSING_USER_MESSAGE
            )

        if request.data.get(AC.KEYS.CHECKOUT) is True:
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

            response_data = self._checkout(basket, payment_processor=payment_processor())
        else:
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
        logger.info(
            u"Froze basket [%d]",
            basket.id,
        )

        response_data = self._generate_basic_response(basket)

        if basket.total_incl_tax == AC.FREE:
            order_metadata = data.get_order_metadata(basket)

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
            payment_data = {
                AC.KEYS.PAYMENT_PROCESSOR_NAME: payment_processor.NAME,
                AC.KEYS.PAYMENT_FORM_DATA: payment_processor.get_transaction_parameters(basket),
                AC.KEYS.PAYMENT_PAGE_URL: payment_processor.payment_page_url,
            }

            response_data[AC.KEYS.PAYMENT_DATA] = payment_data

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


class OrderListView(ListAPIView):
    """Endpoint for listing orders.

    Results are ordered with the newest order being the first in the list of results.
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrderSerializer

    def get_queryset(self):
        return self.request.user.orders.order_by('-date_placed')


class OrderRetrieveView(RetrieveAPIView):
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
    queryset = Order.objects.all()

    def get_object(self):
        """Retrieve the order for this request.

        Retrieves the associated order. If it is associated with the authenticated user, returns it. Otherwise,
        raises an Http404 exception.

        Returns:
            Order: The associated order.

        Raises:
            Http404: Returns a 404 Not Found exception if the request order cannot be found or
                is not associated with the authenticated user.

        """
        order = super(OrderRetrieveView, self).get_object()
        if order and order.user.username == self.request.user.username:
            return order
        else:
            raise Http404


class OrderByBasketRetrieveView(OrderRetrieveView):
    """Allow the viewing of Orders by Basket.

    Works exactly the same as OrderRetrieveView, except that orders are looked
    up via the id of the related basket.
    """
    lookup_field = 'basket_id'


class PaymentProcessorListView(ListAPIView):
    """View that lists the available payment processors."""
    pagination_class = None
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.PaymentProcessorSerializer

    def get_queryset(self):
        """Fetch the list of payment processor classes based on Django settings."""
        return [get_processor_class(path) for path in settings.PAYMENT_PROCESSORS]
