import logging
from functools import cached_property

from django.conf import settings
from edx_rest_framework_extensions.permissions import LoginRedirectIfUnauthenticated
from getsmarter_api_clients.geag import GetSmarterEnterpriseApiClient
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_extensions.cache.decorators import cache_response

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
