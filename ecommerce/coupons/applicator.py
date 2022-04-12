

import logging
from itertools import chain

from oscar.core.loading import get_class, get_model

from ecommerce.extensions.offer.applicator import Applicator as BaseApplicator

logger = logging.getLogger(__name__)
BUNDLE = 'bundle_identifier'

OfferApplications = get_class('offer.results', 'OfferApplications')


class Applicator(BaseApplicator):
    """
    Custom applicator.
    """

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
        enterprise_customer_uuid = getattr(
            basket, 'enterprise_customer_uuid', None
        )
        enterprise_offers = self._get_enterprise_offers(basket.site, user, enterprise_customer_uuid)
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

    def _get_enterprise_offers(self, site, user, enterprise_customer_uuid=None):  # pylint: disable=arguments-differ
        """
        Return enterprise offers filtered by the user's enterprise, if it exists.
        """
        # enterprise_id = get_enterprise_id_for_user(site, user)
        if enterprise_customer_uuid:
            ConditionalOffer = get_model('offer', 'ConditionalOffer')
            offers = ConditionalOffer.active.filter(
                offer_type=ConditionalOffer.SITE,
                condition__enterprise_customer_uuid=enterprise_customer_uuid
            )
            return offers.select_related('condition', 'benefit')

        return []
