

import ddt
from django.core.management import call_command
from django.core.management.base import CommandError
from mock import patch
from oscar.core.loading import get_model
from oscar.test import factories
from testfixtures import LogCapture

from ecommerce.tests.factories import PartnerFactory
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
LOGGER_NAME = 'ecommerce.extensions.offer.management.commands.remove_partner_offers'
OrderLine = get_model('order', 'Line')


@ddt.ddt
class RemovePartnerOffersTests(TestCase):
    """Tests for remove_partner_offers management command."""

    PARTNER_CODE = 'testX'
    YES_NO_PATCH_LOCATION = 'ecommerce.extensions.offer.management.commands.remove_partner_offers.query_yes_no'

    def test_partner_required(self):
        """Test that command raises partner required error."""
        err_msg = 'Error: the following arguments are required: --partner'
        with self.assertRaisesRegex(CommandError, err_msg):
            call_command('remove_partner_offers')

    def test_no_offer_found(self):
        """Test that command logs no offer found."""
        with LogCapture(LOGGER_NAME) as log:
            call_command('remove_partner_offers', '--partner={}'.format(self.PARTNER_CODE))
            log.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'No offer found for partner [{}].'.format(self.PARTNER_CODE)
                )
            )

    @ddt.data(True, False)
    def test_remove_partner_offers(self, yes_no_value):
        """Test that command removes partner offers."""
        partner = PartnerFactory(short_code=self.PARTNER_CODE)
        catalog = Catalog.objects.create(partner=partner)
        offer = factories.ConditionalOfferFactory()
        second_offer = factories.ConditionalOfferFactory(name='Second Offer')
        offer_range = offer.benefit.range
        second_offer_range = second_offer.benefit.range
        offer_range.catalog = second_offer_range.catalog = catalog
        offer_range.save()
        second_offer_range.save()

        offer_names = '1. {offer} \n 2. {second_offer} '.format(offer=offer.name, second_offer=second_offer.name)
        expected = [
            (
                LOGGER_NAME,
                'WARNING',
                'Conditional offers to be deleted for partner [{partner_code}] \n {offer_names}'.format(
                    partner_code=self.PARTNER_CODE,
                    offer_names=offer_names,
                )
            )
        ]

        with patch(self.YES_NO_PATCH_LOCATION) as mocked_yes_no:
            mocked_yes_no.return_value = yes_no_value
            with LogCapture(LOGGER_NAME) as log:
                call_command('remove_partner_offers', '--partner={}'.format(self.PARTNER_CODE))
                if yes_no_value:
                    log_msg = '2 conditional offers removed successfully.'
                else:
                    log_msg = 'Operation canceled.'

                expected.append(
                    (
                        LOGGER_NAME,
                        'INFO',
                        log_msg
                    )
                )
                log.check(*expected)
