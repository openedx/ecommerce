import logging
from urllib.parse import urlencode

import requests
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


class SDNView(APIView):
    """A class that act as a dedicated SDN service."""

    http_method_names = ['get']
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        """
        Searches the OFAC list for an individual with the specified details.
        The check returns zero hits if:
            * request to the SDN API times out
            * SDN API returns a non-200 status code response
            * user is not found on the SDN list

        URL params:
            name (str): Individual's full name.
            city (str): Individual's city.
            country (str): ISO 3166-1 alpha-2 country code where the individual is from.
        Returns:
            dict: SDN API response.
        """
        name = request.GET.get('name')
        city = request.GET.get('city')
        country = request.GET.get('country')
        sdn_list = request.site.siteconfiguration.sdn_api_list

        params_dict = {
            'sources': sdn_list,
            'type': 'individual',
            'name': str(name).encode('utf-8'),
            'city': str(city).encode('utf-8'),
            'countries': country
        }
        params = urlencode(params_dict)

        sdn_check_url = f'{settings.SDN_CHECK_API_URL}?{params}'
        auth_header = {'subscription-key': settings.SDN_CHECK_API_KEY}

        try:
            response = requests.get(
                sdn_check_url,
                headers=auth_header,
                timeout=settings.SDN_CHECK_REQUEST_TIMEOUT
            )
        except requests.exceptions.Timeout:
            error_msg = f'Connection to US Treasury SDN API timed out for {name}.'
            logger.warning(error_msg)
            return Response({
                'msg': error_msg
            })

        if response.status_code != 200:
            logger.warning(
                'Unable to connect to US Treasury SDN API for [%s]. Status code [%d] with message: [%s]',
                name, response.status_code, response.content
            )
            return Response({
                'msg': f'Unable to connect to US Treasury SDN API for {name}. Status code {response.status_code}',
                'response': response.json()
            })

        return Response(response.json())
