import logging
from functools import cached_property
from urllib.parse import urlencode

from django.conf import settings
from django.http import (
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    HttpResponseRedirect,
    HttpResponseServerError
)
from edx_rest_framework_extensions.permissions import LoginRedirectIfUnauthenticated
from getsmarter_api_clients.geag import GetSmarterEnterpriseApiClient
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_extensions.cache.decorators import cache_response

from ecommerce.extensions.basket.utils import apply_offers_on_basket, prepare_basket
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.executive_education_2u.constants import ExecutiveEducation2UCheckoutFailureReason
from ecommerce.extensions.executive_education_2u.utils import (
    get_executive_education_2u_product,
    get_learner_portal_url,
    get_previous_order_for_user
)
from ecommerce.extensions.partner.shortcuts import get_partner_for_site

logger = logging.getLogger(__name__)


class ExecutiveEducation2UViewSet(viewsets.ViewSet):
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

    @action(detail=False, methods=['get', 'post'], url_path='checkout')
    def checkout(self, request):
        partner = get_partner_for_site(request)

        if request.method == 'GET':
            sku = request.query_params.get('sku', '')

            if not sku:
                return HttpResponseBadRequest("SKU not provided.")

            product = get_executive_education_2u_product(partner, sku)
            if not product:
                return HttpResponseNotFound(f"No Executive Education (2U) product found for SKU {sku}.")

            previous_order = get_previous_order_for_user(request.user, product)
            if previous_order:
                # redirect to receipt page
                receipt_path = get_receipt_page_url(
                    self.request,
                    order_number=previous_order.number,
                    site_configuration=previous_order.site.siteconfiguration,
                    disable_back_button=False
                )
                return HttpResponseRedirect(receipt_path)

            try:
                # Apply offers on basket and see if the total cost is $0.
                basket = prepare_basket(request, [product])
                apply_offers_on_basket(request, basket)

                course_uuid = getattr(product.attr, 'UUID', '')
                query_params = {
                    'course_uuid': course_uuid,
                    'sku': sku
                }

                referer = request.headers.get('referer', '')
                if referer:
                    query_params.update({'referer': referer})

                # User cannot purchase Exec Ed 2U products directly.
                if basket.total_excl_tax != 0:
                    query_params.update({
                        'failure_reason': ExecutiveEducation2UCheckoutFailureReason.NO_OFFER_AVAILABLE
                    })
                    basket.flush()

                learner_portal_url = get_learner_portal_url(request)
                # Redirect users to learner portals for terms & policies or error display
                redirect_url = f'{learner_portal_url}?{urlencode(query_params)}'
                return HttpResponseRedirect(redirect_url)
            except Exception as ex:  # pylint: disable=broad-except
                logger.exception(ex)
                return HttpResponseServerError("Something went wrong, please try again later.")
        else:
            return HttpResponseNotAllowed('Not implemented.')
