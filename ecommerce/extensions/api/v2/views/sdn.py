"""DO NOT USE THIS CODE: WILL DEPRECATED IN UPCOMING RELEASE (DEPR-90). API endpoint for performing user SDN check."""
from __future__ import absolute_import

import logging

from oscar.core.loading import get_model
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.extensions.payment.utils import checkSDN

logger = logging.getLogger(__name__)

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
        basket_id = request.basket.id
        hit_count = checkSDN(request, request.data['name'], request.data['city'], request.data['country'])

        if hit_count:
            logger.info(
                'SDNCheck Api called for basket [%d]. It received %d hit(s).',
                basket_id,
                hit_count,
            )
        else:
            logger.info(
                'SDNCheck Api called for basket [%d]. It did not receive a hit.',
                basket_id,
            )
        return Response({'hits': hit_count})
