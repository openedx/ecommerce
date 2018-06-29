"""HTTP endpoints for interacting with baskets."""
from __future__ import unicode_literals

import logging
import warnings

import waffle
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from edx_rest_framework_extensions.permissions import IsSuperuser
from oscar.core.loading import get_class, get_model
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ecommerce.cache_utils.utils import RequestCache, TieredCache
from ecommerce.core.utils import get_cache_key
from ecommerce.enterprise.entitlements import get_entitlement_voucher
from ecommerce.extensions.analytics.utils import audit_log
from ecommerce.extensions.api import data as data_api
from ecommerce.extensions.api import exceptions as api_exceptions
from ecommerce.extensions.api.serializers import OrderSerializer
from ecommerce.extensions.basket.constants import TEMPORARY_BASKET_CACHE_KEY
from ecommerce.extensions.basket.utils import attribute_cookie_data
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.partner.shortcuts import get_partner_for_site
from ecommerce.extensions.payment import exceptions as payment_exceptions
from ecommerce.extensions.payment.helpers import get_default_processor_class, get_processor_class_by_name

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
Product = get_model('catalogue', 'Product')
Selector = get_class('partner.strategy', 'Selector')
User = get_user_model()
Voucher = get_model('voucher', 'Voucher')


class BasketCreateView(EdxOrderPlacementMixin, generics.CreateAPIView):
    """Endpoint for creating baskets.

    If requested, performs checkout operations on baskets, placing an order if
    the contents of the basket are free, and generating payment parameters otherwise.
    """
    permission_classes = (IsAuthenticated,)

    def get_serializer(self):
        pass

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

            attribute_cookie_data(basket, request)

            requested_products = request.data.get('products')
            if requested_products:
                is_multi_product_basket = True if len(requested_products) > 1 else False
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

                    # Call signal handler to notify listeners that something has been added to the basket
                    basket_addition = get_class('basket.signals', 'basket_addition')
                    basket_addition.send(sender=basket_addition, product=product, user=request.user, request=request,
                                         basket=basket, is_multi_product_basket=is_multi_product_basket)
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
                response_data = self._checkout(basket, payment_processor(request.site), request)
            except Exception as ex:  # pylint: disable=broad-except
                basket.delete()
                logger.exception('Failed to initiate checkout for Basket [%d]. The basket has been deleted.', basket_id)
                return Response({'developer_message': ex.message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Return a serialized basket, if checkout was not requested.
            response_data = self._generate_basic_response(basket)

        return Response(response_data, status=status.HTTP_200_OK)

    def _checkout(self, basket, payment_processor, request=None):
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
            order = self.place_free_order(basket, request)

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


class BasketCalculateView(generics.GenericAPIView):
    permission_classes = (IsAuthenticated,)
    MARKETING_USER = 'marketing_site_worker'

    def _calculate_temporary_basket_atomic(self, user, request, products, voucher, skus, code):
        response = None
        try:
            # We wrap this in an atomic operation so we never commit this to the db.
            # This is to avoid merging this temporary basket with a real user basket.
            with transaction.atomic():
                basket = Basket(owner=user, site=request.site)
                basket.strategy = Selector().strategy(user=user, request=request)

                for product in products:
                    basket.add_product(product, 1)

                if voucher:
                    basket.vouchers.add(voucher)

                # Calculate any discounts on the basket.
                Applicator().apply(basket, user=user, request=request)

                discounts = []
                if basket.offer_discounts:
                    discounts = basket.offer_discounts
                if basket.voucher_discounts:
                    discounts.extend(basket.voucher_discounts)

                response = {
                    'total_incl_tax_excl_discounts': basket.total_incl_tax_excl_discounts,
                    'total_incl_tax': basket.total_incl_tax,
                    'currency': basket.currency
                }
                raise api_exceptions.TemporaryBasketException
        except api_exceptions.TemporaryBasketException:
            pass
        except:  # pylint: disable=bare-except
            logger.exception(
                'Failed to calculate basket discount for SKUs [%s] and voucher [%s].',
                skus, code
            )
            raise
        return response

    def _calculate_temporary_basket(self, user, request, products, voucher, skus, code):
        # TODO: LEARNER-5197: Delete the "pragma: no cover" pragmas from this function
        # once the disable_calculate_temporary_basket_atomic_transaction waffle flag has
        # been removed.
        response = None
        basket = None

        try:
            basket = Basket(owner=user, site=request.site)
            basket.strategy = Selector().strategy(user=user)

            for product in products:
                basket.add_product(product, 1)

            if voucher:  # pragma: no cover
                basket.vouchers.add(voucher)

            # Calculate any discounts on the basket.
            Applicator().apply(basket, user=user, request=request)

            discounts = []
            if basket.offer_discounts:  # pragma: no cover
                discounts = basket.offer_discounts
            if basket.voucher_discounts:  # pragma: no cover
                discounts.extend(basket.voucher_discounts)

            response = {
                'total_incl_tax_excl_discounts': basket.total_incl_tax_excl_discounts,
                'total_incl_tax': basket.total_incl_tax,
                'currency': basket.currency
            }
        except:  # pylint: disable=bare-except
            logger.exception(
                'Failed to calculate basket discount for SKUs [%s] and voucher [%s].',
                skus, code
            )
            raise
        finally:
            if basket:
                basket.delete()

        return response

    @transaction.non_atomic_requests
    def get(self, request):  # pylint: disable=too-many-statements
        """ Calculate basket totals given a list of sku's

        Create a temporary basket add the sku's and apply an optional voucher code.
        Then calculate the total price less discounts. If a voucher code is not
        provided apply a voucher in the Enterprise entitlements available
        to the user.

        Query Params:
            sku (string): A list of sku(s) to calculate
            code (string): Optional voucher code to apply to the basket.
            username (string): Optional username of a user for which to calculate the basket.

        Returns:
            JSON: {
                    'total_incl_tax_excl_discounts': basket.total_incl_tax_excl_discounts,
                    'total_incl_tax': basket.total_incl_tax,
                    'currency': basket.currency
                }
        """
        RequestCache.set(TEMPORARY_BASKET_CACHE_KEY, True)  # TODO: LEARNER 5463

        partner = get_partner_for_site(request)
        skus = request.GET.getlist('sku')
        if not skus:
            return HttpResponseBadRequest(_('No SKUs provided.'))
        skus.sort()

        code = request.GET.get('code', None)
        try:
            voucher = Voucher.objects.get(code=code) if code else None
        except Voucher.DoesNotExist:
            voucher = None

        products = Product.objects.filter(stockrecords__partner=partner, stockrecords__partner_sku__in=skus)
        if not products:
            return HttpResponseBadRequest(_('Products with SKU(s) [{skus}] do not exist.').format(skus=', '.join(skus)))

        # If there is only one product apply an Enterprise entitlement voucher
        if not voucher and len(products) == 1:
            voucher = get_entitlement_voucher(request, products[0])

        basket_owner = request.user

        requested_username = request.GET.get('username', default='')
        is_anonymous = request.GET.get('is_anonymous', 'false').lower() == 'true'

        use_default_basket = is_anonymous

        # validate query parameters
        if requested_username and is_anonymous:
            return HttpResponseBadRequest(_('Provide username or is_anonymous query param, but not both'))
        elif not requested_username and not is_anonymous:
            logger.warning("Request to Basket Calculate must supply either username or is_anonymous query"
                           " param. Requesting user=%s. Future versions of this API will treat this "
                           "WARNING as an ERROR and raise an exception.", basket_owner.username)
            requested_username = request.user.username

        # If a username is passed in, validate that the user has staff access or is the same user.
        if requested_username:
            if basket_owner.username.lower() == requested_username.lower():
                pass
            elif basket_owner.is_staff:
                try:
                    basket_owner = User.objects.get(username=requested_username)
                except User.DoesNotExist:
                    # This case represents a user who is logged in to marketing, but
                    # doesn't yet have an account in ecommerce. These users have
                    # never purchased before.
                    use_default_basket = True
            else:
                return HttpResponseForbidden('Unauthorized user credentials')

        if basket_owner.username == self.MARKETING_USER and not use_default_basket:
            # For legacy requests that predate is_anonymous parameter, we will calculate
            # an anonymous basket if the calculated user is the marketing user.
            # TODO: LEARNER-5057: Remove this special case for the marketing user
            # once logs show no more requests with no parameters (see above).
            use_default_basket = True

        if use_default_basket:
            basket_owner = None

        cache_key = None
        if use_default_basket:
            # For an anonymous user we can directly get the cached price, because
            # there can't be any enrollments or entitlements.
            cache_key = get_cache_key(
                site_comain=request.site,
                resource_name='calculate',
                skus=skus
            )
            cached_response = TieredCache.get_cached_response(cache_key)
            if cached_response.is_hit:
                return Response(cached_response.value)

        if waffle.flag_is_active(request, "disable_calculate_temporary_basket_atomic_transaction"):
            response = self._calculate_temporary_basket(basket_owner, request, products, voucher, skus, code)
        else:
            response = self._calculate_temporary_basket_atomic(basket_owner, request, products, voucher, skus, code)

        if response and use_default_basket:
            TieredCache.set_all_tiers(cache_key, response, settings.ANONYMOUS_BASKET_CALCULATE_CACHE_TIMEOUT)

        return Response(response)
