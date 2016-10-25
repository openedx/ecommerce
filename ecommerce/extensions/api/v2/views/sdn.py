"""API endpoint for performing an SDN check on users."""
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ecommerce.extensions.payment.utils import SDNClient


class SDNCheckViewSet(APIView):
    """Performs an SDN check for a given user."""
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """
        POST handler for the view. User data is posted to this handler
        which performs an SDN check and returns whether the user passed
        or failed.
        """
        name = request.data['name']
        country = request.data['country']
        hits = 0

        site_configuration = request.site.siteconfiguration
        if site_configuration.enable_sdn_check:
            sdn_check = SDNClient(
                api_url=site_configuration.sdn_api_url,
                api_key=site_configuration.sdn_api_key,
                sdn_list=site_configuration.sdn_api_list
            )
            response = sdn_check.search(name, country)
            hits = response['total']
            if hits > 0:
                sdn_check.deactivate_user(
                    request.user,
                    request.site.siteconfiguration,
                    name,
                    country,
                    response
                )

        return Response({'hits': hits})
