from __future__ import absolute_import

import logging
from itertools import chain

import waffle
from oscar.apps.offer.applicator import Applicator
from oscar.core.loading import get_model

from ecommerce.enterprise.utils import get_enterprise_id_for_user
from ecommerce.extensions.offer.constants import CUSTOM_APPLICATOR_LOG_FLAG

logger = logging.getLogger(__name__)
BUNDLE = 'bundle_identifier'


class CustomApplicator(Applicator):
    """
    Custom applicator for applying offers to program baskets and voucher baskets.
    """

    def apply(self, basket, user=None, request=None, bundle_id=None):  # pylint: disable=arguments-differ
        """
        Apply all relevant offers to the given basket.

        Args:
            basket (Basket): The basket to check for eligible vouchers/offers.
            user (User): The user whose basket we are checking.
            request (Request): The request is passed as sometimes the available offers
                are dependent on the user (eg session-based offers).
            bundle_id (int): (Optional) The bundle_id of the basket. This should only be
                used in the case of a temporary basket which is not saved to the db, because
                we get an error when trying to create the bundle_id BasketAttribute.
        """
        offers = self._get_offers(basket, user, request, bundle_id)
        self.apply_offers(basket, offers)

    def _get_offers(self, basket, user=None, request=None, bundle_id=None):
        """
        Returns all offers to apply to the basket.

        If the basket has a bundle, i.e. a program, gets only the site offers
        associated with that specific bundle, rather than all site offers.
        Otherwise, Gets the site offers not associated with a bundle.

        Returns:
            list of Offer: A sorted list of all the offers that apply to the
                basket.
        """
        BasketAttribute = get_model('basket', 'BasketAttribute')
        BasketAttributeType = get_model('basket', 'BasketAttributeType')

        bundle_attributes = BasketAttribute.objects.filter(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=BUNDLE)
        )
        program_uuid = bundle_id if bundle_attributes.count() == 0 else bundle_attributes.first().value_text

        if program_uuid:
            program_offers = self._get_program_offers(program_uuid)
            site_offers = []
            if waffle.flag_is_active(request, CUSTOM_APPLICATOR_LOG_FLAG):
                logger.warning(
                    'CustomApplicator processed Basket [%s] from Request [%s] and User [%s] with a bundle.',
                    basket, request, user,
                )
        else:
            if waffle.flag_is_active(request, CUSTOM_APPLICATOR_LOG_FLAG):
                logger.warning(
                    'CustomApplicator processed Basket [%s] from Request [%s] and User [%s] without a bundle.',
                    basket, request, user,
                )
            program_offers = []
            site_offers = self.get_site_offers()

        basket_offers = self.get_basket_offers(basket, user)

        # edX currently does not use user offers or session offers.
        # The default oscar implementations which return [] are here in case edX ever starts using these offers.
        enterprise_offers = self._get_enterprise_offers(basket.site, user)
        user_offers = self.get_user_offers(user)
        session_offers = self.get_session_offers(request)

        return list(
            sorted(
                chain(session_offers, basket_offers, user_offers, program_offers, enterprise_offers, site_offers),
                key=lambda o: o.priority,
                reverse=True,
            )
        )

    def get_site_offers(self):
        """
        Return site offers that are available to baskets without bundle ids.
        """
        ConditionalOffer = get_model('offer', 'ConditionalOffer')
        qs = ConditionalOffer.active.filter(
            offer_type=ConditionalOffer.SITE,
            condition__program_uuid__isnull=True,
            condition__enterprise_customer_uuid__isnull=True,
        )
        return qs.select_related('condition', 'benefit')

    def _get_enterprise_offers(self, site, user):
        """
        Return enterprise offers filtered by the user's enterprise, if it exists.
        """
        enterprise_id = get_enterprise_id_for_user(site, user)
        if enterprise_id:
            ConditionalOffer = get_model('offer', 'ConditionalOffer')
            offers = ConditionalOffer.active.filter(
                offer_type=ConditionalOffer.SITE,
                condition__enterprise_customer_uuid=enterprise_id
            )
            return offers.select_related('condition', 'benefit')

        return []

    def _get_program_offers(self, bundle_id):
        """
        Returns offers that apply to the program by matching the bundle id.

        Args:
            bundle_id: Bundle ID to get program bundling for this basket.

        Returns:
            list of Offer: List of all the offers applicable to the program.
        """
        ConditionalOffer = get_model('offer', 'ConditionalOffer')
        offers = ConditionalOffer.active.filter(offer_type=ConditionalOffer.SITE, condition__program_uuid=bundle_id)

        return offers.select_related('condition', 'benefit')
