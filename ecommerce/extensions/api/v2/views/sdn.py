import logging
from urllib.parse import urlencode

import requests
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

logger = logging.getLogger(__name__)


class SDNView(APIView):
    http_method_names = ['get']
    permission_classes = (IsAuthenticated,)

    def get(self, request):
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
            logger.warning('Connection to US Treasury SDN API timed out for [%s].', name)
            raise

        if response.status_code != 200:
            print(response)
            logger.warning(
                'Unable to connect to US Treasury SDN API for [%s]. Status code [%d] with message: [%s]',
                name, response.status_code, response.content
            )
            raise requests.exceptions.HTTPError('Unable to connect to SDN API')

        return response.json()
