

import logging
from itertools import chain

from oscar.apps.offer.applicator import Applicator as OscarApplicator
from oscar.core.loading import get_model

from ecommerce.enterprise.api import get_enterprise_id_for_user

logger = logging.getLogger(__name__)
BUNDLE = 'bundle_identifier'


class Applicator(OscarApplicator):
    """
    Custom applicator for more intelligently applying offers to baskets.

    This applicator uses logic to prefilter the offers, rather than blindly
    returning every offer, including ones that could never apply.

    This extension Applicator will be used when you use the following:

        Applicator = get_class('offer.applicator', 'Applicator')
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
        offers = self.get_offers(basket, user, request, bundle_id)
        self.apply_offers(basket, offers)

    def get_offers(self, basket, user=None, request=None, bundle_id=None):  # pylint: disable=arguments-differ
        """
        Returns all offers to apply to the basket.

        Does prefiltering to filter out offers that could never apply to a particular
        basket. As an example, if the basket has a bundle ID or an enterprise customer
        UUID, gets only the site offers associated with that specific bundle or enterprise
        customer, rather than all site offers. Otherwise, gets the site offers not associated
        with a bundle.

        Returns:
            list of Offer: A sorted list of all the offers that apply to the basket.
        """
        program_offers = self._get_program_offers(basket, bundle_id)
        enterprise_offers = self._get_enterprise_offers(basket.site, user)
        site_offers = [] if program_offers or enterprise_offers else self.get_site_offers()

        basket_offers = self.get_basket_offers(basket, user)

        # edX currently does not use user offers or session offers.
        # The default oscar implementations which return [] are here in case edX ever starts using these offers.
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
        Return other site offers that are available to baskets without bundle ids or
        enterprise customer UUIDs.

        Excludes: Bundle and Enterprise offers.
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

    def _get_program_offers(self, basket, bundle_id):
        """
        Returns offers that apply to the program by matching the bundle id.

        Args:
            bundle_id: Bundle ID to get program bundling for this basket.

        Returns:
            list of Offer: List of all the offers applicable to the program.
        """
        BasketAttribute = get_model('basket', 'BasketAttribute')
        BasketAttributeType = get_model('basket', 'BasketAttributeType')
        ConditionalOffer = get_model('offer', 'ConditionalOffer')

        bundle_attributes = BasketAttribute.objects.filter(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=BUNDLE)
        )
        program_uuid = bundle_id if bundle_attributes.count() == 0 else bundle_attributes.first().value_text
        if program_uuid:
            offers = ConditionalOffer.active.filter(
                offer_type=ConditionalOffer.SITE, condition__program_uuid=program_uuid
            )
            return offers.select_related('condition', 'benefit')

        return []
