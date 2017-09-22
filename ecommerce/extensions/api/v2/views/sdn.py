"""API endpoint for performing an SDN check on users."""
from django.contrib.auth import logout
from oscar.core.loading import get_model
from requests.exceptions import HTTPError, Timeout
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.payment.utils import SDNClient

Basket = get_model('basket', 'Basket')


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
        city = request.data['city']
        country = request.data['country']
        hits = 0

        site_configuration = request.site.siteconfiguration
        basket = Basket.get_basket(request.user, site_configuration.site)

        if site_configuration.enable_sdn_check:
            sdn_check = SDNClient(
                api_url=site_configuration.sdn_api_url,
                api_key=site_configuration.sdn_api_key,
                sdn_list=site_configuration.sdn_api_list
            )
            try:
                response = sdn_check.search(name, city, country)
                hits = response['total']
                if hits > 0:
                    sdn_check.deactivate_user(
                        basket,
                        name,
                        city,
                        country,
                        response
                    )
                    logout(request)
            except (HTTPError, Timeout):
                # If the SDN API endpoint is down or times out
                # the user is allowed to make the purchase.
                pass

        return Response({'hits': hits})
