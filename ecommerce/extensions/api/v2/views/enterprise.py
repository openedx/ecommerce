from edx_rest_api_client.client import EdxRestApiClient
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from ecommerce.courses.utils import traverse_pagination


class EnterpriseCustomerViewSet(generics.GenericAPIView):

    permission_classes = (IsAuthenticated, IsAdminUser,)

    def get(self, request):
        site = request.site
        return Response(data={'results': get_enterprise_customers(site, token=request.user.access_token)})


def get_enterprise_customers(site, token):
    resource = 'enterprise-customer'
    client = EdxRestApiClient(
        site.siteconfiguration.enterprise_api_url,
        oauth_access_token=token
    )
    endpoint = getattr(client, resource)
    response = endpoint.get()
    return [
        {
            'name': each['name'],
            'id': each['uuid'],
        }
        for each in traverse_pagination(response, endpoint)
    ]
