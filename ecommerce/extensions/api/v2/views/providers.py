"""HTTP endpoint for displaying information about providers."""


import logging

from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.api.serializers import ProviderSerializer
from ecommerce.extensions.checkout.utils import get_credit_provider_details

logger = logging.getLogger(__name__)


class ProviderViewSet(APIView):
    """Gets the credit provider data from LMS"""
    def get(self, request):
        credit_provider_id = request.GET.get('credit_provider_id')
        provider_data = get_credit_provider_details(
            credit_provider_id=credit_provider_id,
            site_configuration=request.site.siteconfiguration
        )
        if not provider_data:
            response_data = None
        elif isinstance(provider_data, dict):
            response_data = ProviderSerializer(provider_data).data
        else:
            response_data = ProviderSerializer(provider_data, many=True).data
        return Response(response_data)
