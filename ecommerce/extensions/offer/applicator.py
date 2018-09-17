import logging
from itertools import chain

import waffle
from oscar.apps.offer.applicator import Applicator
from oscar.core.loading import get_model

from ecommerce.extensions.offer.constants import PROGRAM_APPLICATOR_LOG_FLAG

logger = logging.getLogger(__name__)
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
BUNDLE = 'bundle_identifier'


class ProgramApplicator(Applicator):
    """
    Custom applicator for applying offers to programs.
    """

    def get_offers(self, basket, user=None, request=None):
        """
        Returns all offers to apply to the basket.

        If the basket has a bundle, i.e. a program, gets only the site offers
        associated with that specific bundle, rather than all site offers.
        Otherwise, behaves like the regular Oscar applicator.

        Args:
            basket (Basket): The basket to check for eligible
                vouchers/offers.
            user (User): The user whose basket we are checking.
            request (Request): Request object.

        Returns:
            list of Offer: A sorted list of all the offers that apply to the
                basket.
        """
        bundle_attributes = BasketAttribute.objects.filter(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=BUNDLE)
        )
        if bundle_attributes.count() > 0:
            program_offers = self.get_program_offers(bundle_attributes.first())
            site_offers = []
        else:
            if waffle.flag_is_active(request, PROGRAM_APPLICATOR_LOG_FLAG):
                logger.warning(
                    'ProgramApplicator processed Basket [%s] from Request [%s] and User [%s] without a bundle meaning'
                    ' all site offers were considered.', basket, request, user,
                )
            program_offers = []
            site_offers = self.get_site_offers()

        basket_offers = self.get_basket_offers(basket, user)

        # edX currently does not use user offers or session offers.
        # The default oscar implementations which return [] are here in case edX ever starts using these offers.
        user_offers = self.get_user_offers(user)
        session_offers = self.get_session_offers(request)

        return list(
            sorted(
                chain(session_offers, basket_offers, user_offers, program_offers, site_offers),
                key=lambda o: o.priority,
                reverse=True,
            )
        )

    def get_program_offers(self, bundle_attribute):
        """
        Returns offers that apply to the program by matching the bundle id.

        Args:
            bundle_attribute (BasketAttribute): The BasketAttribute object
                associated with program bundling for this basket.

        Returns:
            list of Offer: List of all the offers applicable to the program.
        """
        bundle_id = bundle_attribute.value_text
        ConditionalOffer = get_model('offer', 'ConditionalOffer')
        offers = ConditionalOffer.active.filter(offer_type=ConditionalOffer.SITE, condition__program_uuid=bundle_id)

        return offers.select_related('condition', 'benefit')
