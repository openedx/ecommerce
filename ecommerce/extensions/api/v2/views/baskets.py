"""HTTP endpoints for interacting with baskets."""
from __future__ import unicode_literals

import logging
import warnings

from django.db import transaction
from django.utils.decorators import method_decorator
from edx_rest_framework_extensions.permissions import IsSuperuser
from oscar.core.loading import get_class, get_model
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ecommerce.extensions.analytics.utils import audit_log
from ecommerce.extensions.api import data as data_api, exceptions as api_exceptions
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment import exceptions as payment_exceptions
from ecommerce.extensions.payment.helpers import (get_default_processor_class, get_processor_class_by_name)

Basket = get_model('basket', 'Basket')
logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class BasketCreateView(EdxOrderPlacementMixin, generics.CreateAPIView):
    """Endpoint for creating baskets.

    If requested, performs checkout operations on baskets, placing an order if
    the contents of the basket are free, and generating payment parameters otherwise.
    """
    permission_classes = (IsAuthenticated,)

    # Disable atomicity for the view. Otherwise, we'd be unable to commit to the database
    # until the request had concluded; Django will refuse to commit when an atomic() block
    # is active, since that would break atomicity. Without an order present in the database
    # at the time fulfillment is attempted, asynchronous order fulfillment tasks will fail.
    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(BasketCreateView, self).dispatch(request, *args, **kwargs)

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
                'id': 7,
                'order': None,
                'payment_data': None
            }

            If the product with SKU 'FREE-SEAT' is free and checkout is desired:

            >>> data = {'products': [{'sku': 'FREE-SEAT'}], 'checkout': True, 'payment_processor_name': 'paypal'}
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> response.json()
            {
                'id': 7,
                'order': {'number': 'OSCR-100007'},
                'payment_data': None
            }

            If the product with SKU 'PAID-SEAT' is not free and checkout is desired:

            >>> data = {'products': [{'sku': 'PAID-SEAT'}], 'checkout': True, 'payment_processor_name': 'paypal'}
            >>> response = requests.post(url, data=json.dumps(data), headers=headers)
            >>> response.json()
            {
                'id': 7,
                'order': None,
                'payment_data': {
                    'payment_processor_name': 'paypal',
                    'payment_form_data': {...},
                    'payment_page_url': 'https://www.someexternallyhostedpaymentpage.com'
                }
            }
        """
        # Explicitly delimit operations which will be rolled back if an exception occurs.
        # atomic() context managers restore atomicity at points where we are modifying data
        # (baskets, then orders) to ensure that we don't leave the system in a dirty state
        # in the event of an error.
        with transaction.atomic():
            basket = Basket.create_basket(request.site, request.user)
            basket_id = basket.id

            requested_products = request.data.get('products')
            if requested_products:
                for requested_product in requested_products:
                    # Ensure the requested products exist
                    sku = requested_product.get('sku')
                    if sku:
                        try:
                            product = data_api.get_product(sku)
                        except api_exceptions.ProductNotFoundError as error:
                            return self._report_bad_request(
                                error.message,
                                api_exceptions.PRODUCT_NOT_FOUND_USER_MESSAGE
                            )
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
                    logger.info('Added product with SKU [%s] to basket [%d]', sku, basket_id)
            else:
                # If no products were included in the request, we cannot checkout.
                return self._report_bad_request(
                    api_exceptions.PRODUCT_OBJECTS_MISSING_DEVELOPER_MESSAGE,
                    api_exceptions.PRODUCT_OBJECTS_MISSING_USER_MESSAGE
                )

        if request.data.get('checkout') is True:
            # Begin the checkout process, if requested, with the requested payment processor.
            payment_processor_name = request.data.get('payment_processor_name')
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
                basket.delete()
                logger.exception('Failed to initiate checkout for Basket [%d]. The basket has been deleted.', basket_id)
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

        if basket.total_excl_tax == 0:
            order = self.place_free_order(basket)

            # Note: Our order serializer could be used here, but in an effort to pare down the information
            # returned by this endpoint, simply returning the order number will suffice for now.
            response_data['order'] = {'number': order.number}
        else:
            parameters = payment_processor.get_transaction_parameters(basket, request=self.request)
            payment_page_url = parameters.pop('payment_page_url')

            response_data['payment_data'] = {
                'payment_processor_name': payment_processor.NAME,
                'payment_form_data': parameters,
                'payment_page_url': payment_page_url,
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
            'id': basket.id,
            'order': None,
            'payment_data': None,
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


class OrderByBasketRetrieveView(generics.RetrieveAPIView):
    """Allow the viewing of Orders by Basket. """
    permission_classes = (IsAuthenticated,)
    serializer_class = OrderSerializer
    lookup_field = 'number'
    queryset = Order.objects.all()

    def dispatch(self, request, *args, **kwargs):
        msg = 'The basket-order API view is deprecated. Use the order API (e.g. /api/v2/orders/<order-number>/).'
        warnings.warn(msg, DeprecationWarning)
        # Change the basket ID to an order number.
        partner = request.site.siteconfiguration.partner
        kwargs['number'] = OrderNumberGenerator().order_number_from_basket_id(partner, kwargs['basket_id'])
        return super(OrderByBasketRetrieveView, self).dispatch(request, *args, **kwargs)

    def filter_queryset(self, queryset):
        queryset = super(OrderByBasketRetrieveView, self).filter_queryset(queryset)
        user = self.request.user

        # Non-staff users should only see their own orders
        if not user.is_staff:
            queryset = queryset.filter(user=user)

        return queryset


class BasketDestroyView(generics.DestroyAPIView):
    lookup_url_kwarg = 'basket_id'
    permission_classes = (IsAuthenticated, IsSuperuser,)
    queryset = Basket.objects.all()
