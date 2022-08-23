import logging
from functools import cached_property
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseNotFound, HttpResponseRedirect, HttpResponseServerError
from edx_rest_framework_extensions.permissions import LoginRedirectIfUnauthenticated
from getsmarter_api_clients.geag import GetSmarterEnterpriseApiClient
from oscar.core.loading import get_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_extensions.cache.decorators import cache_response

from ecommerce.courses.utils import get_course_info_from_catalog
from ecommerce.enterprise.api import fetch_enterprise_catalogs_for_content_items, get_enterprise_id_for_user
from ecommerce.enterprise.conditions import is_offer_max_discount_available, is_offer_max_user_discount_available
from ecommerce.extensions.analytics.utils import track_segment_event
from ecommerce.extensions.basket.utils import apply_offers_on_basket
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.executive_education_2u.constants import (
    ExecutiveEducation2UCheckoutFailureReason,
    ExecutiveEducation2UCheckoutSegmentEvents
)
from ecommerce.extensions.executive_education_2u.exceptions import EmptyBasketException
from ecommerce.extensions.executive_education_2u.mixins import ExecutiveEducation2UOrderPlacementMixin
from ecommerce.extensions.executive_education_2u.serializers import CheckoutActionSerializer
from ecommerce.extensions.executive_education_2u.utils import (
    get_enterprise_offers_for_catalogs,
    get_executive_education_2u_product,
    get_learner_portal_url,
    get_previous_order_for_user
)
from ecommerce.extensions.partner.shortcuts import get_partner_for_site

logger = logging.getLogger(__name__)
Basket = get_model('basket', 'Basket')


class ExecutiveEducation2UViewSet(viewsets.ViewSet, ExecutiveEducation2UOrderPlacementMixin):
    permission_classes = (LoginRedirectIfUnauthenticated,)

    TERMS_CACHE_TIMEOUT = 60 * 15
    TERMS_CACHE_KEY = 'executive-education-terms'

    @cached_property
    def get_smarter_client(self):
        return GetSmarterEnterpriseApiClient(
            client_id=settings.GET_SMARTER_OAUTH2_KEY,
            client_secret=settings.GET_SMARTER_OAUTH2_SECRET,
            provider_url=settings.GET_SMARTER_OAUTH2_PROVIDER_URL,
            api_url=settings.GET_SMARTER_API_URL
        )

    @cache_response(
        TERMS_CACHE_TIMEOUT,
        key_func=lambda *args, **kwargs: ExecutiveEducation2UViewSet.TERMS_CACHE_KEY,
        cache_errors=False,
    )
    @action(detail=False, methods=['get'], url_path='terms')
    def get_terms_and_policies(self, _):
        """
        Fetch and return the terms and policies.
        """
        try:
            terms = self.get_smarter_client.get_terms_and_policies()
            return Response(terms)
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(ex)
            return Response('Failed to retrieve terms and policies.', status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_receipt_page_url(self, request, user, product):
        """
        Return the link to the receipt page if the product was purchased previously by the user.
        """
        previous_order = get_previous_order_for_user(user, product)
        if previous_order:
            return get_receipt_page_url(
                request,
                order_number=previous_order.number,
                site_configuration=previous_order.site.siteconfiguration,
                disable_back_button=False
            )

        return None

    def _prepare_basket(self, request, product):
        """
        Get user's basket, empty it, and add the given product to the basket.

        Raises:
            EmptyBasketException: If the user has purchased the product previously.
        """
        basket = Basket.get_basket(request.user, request.site)
        basket.flush()

        if not get_previous_order_for_user(request.user, product) and basket.product_quantity(product) == 0:
            basket.add_product(product, 1)

        if not basket.lines.exists():
            logger.error("User has an empty basket. User id: [%d].", request.user.id)
            raise EmptyBasketException

        basket.reset_offer_applications()
        apply_offers_on_basket(request, basket)
        return basket

    def _get_checkout_failure_reason(self, request, basket, product):
        try:
            enterprise_id = get_enterprise_id_for_user(request.site, request.user)
            course_info = get_course_info_from_catalog(request.site, product)
            course_key = course_info['key']

            catalog_list = fetch_enterprise_catalogs_for_content_items(
                request.site,
                course_key,
                enterprise_id
            )

            enterprise_offers = get_enterprise_offers_for_catalogs(enterprise_id, catalog_list)
            if not enterprise_offers:
                return ExecutiveEducation2UCheckoutFailureReason.NO_OFFER_AVAILABLE

            offers_with_remaining_balance = [
                offer for offer in enterprise_offers
                if is_offer_max_discount_available(
                    basket, offer
                )
            ]
            if not offers_with_remaining_balance:
                return ExecutiveEducation2UCheckoutFailureReason.NO_OFFER_WITH_ENOUGH_BALANCE

            offers_with_remaining_user_balance = [
                offer for offer in offers_with_remaining_balance
                if is_offer_max_user_discount_available(
                    basket, offer
                )
            ]

            if not offers_with_remaining_user_balance:
                return ExecutiveEducation2UCheckoutFailureReason.NO_OFFER_WITH_ENOUGH_USER_BALANCE
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(ex)

        # We could end up here if there was an error calling discovery/enterprise-catalog
        return ExecutiveEducation2UCheckoutFailureReason.SYSTEM_ERROR

    @action(detail=False, methods=['get'], url_path='checkout')
    def begin_checkout(self, request):
        """
        Redirect users to the learner portal where they will accept terms & policies and fill out personal information.
        """
        partner = get_partner_for_site(request)
        sku = request.query_params.get('sku', '')

        if not sku:
            return HttpResponseBadRequest('SKU not provided.')

        product = get_executive_education_2u_product(partner, sku)
        if not product:
            return HttpResponseNotFound(f'No Executive Education (2U) product found for SKU {sku}.')

        try:
            # Create basket and see if total cost is $0
            basket = self._prepare_basket(request, product)
            course_uuid = getattr(product.attr, 'UUID', '')

            # Create the query params that will be used by the learner portal
            query_params = {
                'course_uuid': course_uuid,
                'sku': sku
            }

            referer = request.headers.get('referer', '')
            if referer:
                query_params.update({'http_referer': referer})

            failure_reason = None
            # Users cannot purchase Exec Ed 2U products directly
            if basket.total_excl_tax != 0:
                failure_reason = self._get_checkout_failure_reason(request, basket, product)
                query_params.update({
                    'failure_reason': failure_reason
                })
                basket.flush()

            # Redirect users to learner portals for terms & policies or error display
            learner_portal_url = get_learner_portal_url(request)
            redirect_url = f'{learner_portal_url}?{urlencode(query_params)}'

            if failure_reason:
                track_segment_event(
                    request.site,
                    request.user,
                    ExecutiveEducation2UCheckoutSegmentEvents.REDIRECTED_TO_LP_WITH_ERROR,
                    {'failure_reason': failure_reason}
                )
            else:
                track_segment_event(
                    request.site,
                    request.user,
                    ExecutiveEducation2UCheckoutSegmentEvents.REDIRECTED_TO_LP, {}
                )

            return HttpResponseRedirect(redirect_url)
        except EmptyBasketException:
            # Redirect user to receipt page since the product has been purchased previously
            receipt_page_url = self._get_receipt_page_url(self.request, request.user, product)
            track_segment_event(
                request.site,
                request.user,
                ExecutiveEducation2UCheckoutSegmentEvents.REDIRECTED_TO_RECEIPT_PAGE, {}
            )
            return HttpResponseRedirect(receipt_page_url)
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(ex)
            return HttpResponseServerError('Something went wrong, please try again later.')

    @begin_checkout.mapping.post
    def finish_checkout(self, request):
        CheckoutActionSerializer(data=request.data).is_valid(raise_exception=True)

        partner = get_partner_for_site(request)
        sku = request.data['sku']
        product = get_executive_education_2u_product(partner, sku)
        if not product:
            return Response(
                f'No Executive Education (2U) product found for SKU {sku}.',
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            basket = self._prepare_basket(request, product)
            if basket.total_excl_tax != 0:
                logger.exception(
                    'Failed to create a subsidized order for Executive Education (2U) products. '
                    'Basket id: [%d], User id: [%d]',
                    basket.id, request.user.id
                )

                return Response('Failed to create subsidized order.', status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            order = self.place_free_order(
                basket=basket,
                address=request.data.get('address', {}),
                user_details={**request.data['user_details'], 'email': request.user.email},
                terms_accepted_at=request.data['terms_accepted_at'],
                request=request
            )

            track_segment_event(request.site, request.user, ExecutiveEducation2UCheckoutSegmentEvents.ORDER_CREATED, {
                'order_number': order.number
            })

            data = {
                'receipt_page_url': get_receipt_page_url(
                    request,
                    order_number=order.number,
                    site_configuration=order.site.siteconfiguration,
                    disable_back_button=False
                )
            }
            return Response(data, status=status.HTTP_200_OK)
        except EmptyBasketException:
            return Response('User has already purchased the product.', status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except Exception as ex:  # pylint: disable=broad-except
            logger.exception(ex)
            return Response('Something went wrong, please try again later.', status.HTTP_500_INTERNAL_SERVER_ERROR)
