import json
import logging

from django.db import transaction

from ecommerce.extensions.api import data as data_api
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin

logger = logging.getLogger(__name__)


class ExecutiveEducation2UOrderPlacementMixin(EdxOrderPlacementMixin):
    def place_free_order(
        self,
        basket,
        address,
        user_details,
        terms_accepted_at,
        data_share_consent,
        request=None,
    ):  # pylint: disable=arguments-differ
        """
        Fulfill a free order and create a note containing fulfillment info.

        Arguments:
            basket(Basket): the free basket.

        Returns:
            order(Order): the fulfilled order.

        Raises:
            BasketNotFreeError: if the basket is not free.
        """

        if basket.total_incl_tax != 0:
            raise BasketNotFreeError

        basket.freeze()

        order_metadata = data_api.get_order_metadata(basket)

        logger.info(
            'Preparing to place order [%s] for the contents of basket [%d]',
            order_metadata['number'],
            basket.id,
        )
        dsc = str(data_share_consent).lower()
        fulfillment_details = json.dumps({
            'address': address,
            'user_details': user_details,
            'terms_accepted_at': terms_accepted_at,
            'data_share_consent': dsc,
        })

        # Place an order. If order placement succeeds, the order is committed
        # to the database so that it can be fulfilled asynchronously.
        with transaction.atomic():
            order = self.place_order(
                basket=basket,
                billing_address=None,
                order_number=order_metadata['number'],
                order_total=order_metadata['total'],
                request=request,
                shipping_address=None,
                shipping_charge=order_metadata['shipping_charge'],
                shipping_method=order_metadata['shipping_method'],
                user=basket.owner
            )

            # Create a note with information required to fulfill the order
            order.notes.create(message=fulfillment_details, note_type='Fulfillment Details')
            basket.submit()

        return self.handle_successful_order(order, request)
