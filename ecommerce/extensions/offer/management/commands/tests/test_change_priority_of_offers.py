

import ddt
from django.core.management import call_command
from mock import patch
from oscar.core.loading import get_model
from oscar.test import factories
from testfixtures import LogCapture

from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
ConditionalOffer = get_model('offer', 'ConditionalOffer')
LOGGER_NAME = 'ecommerce.extensions.offer.management.commands.change_priority_of_offers'
OrderLine = get_model('order', 'Line')


@ddt.ddt
class ChangeOffersPriorityTests(TestCase):
    """Tests for change_priority_of_offers management command."""

    YES_NO_PATCH_LOCATION = 'ecommerce.extensions.offer.management.commands.change_priority_of_offers.query_yes_no'

    def test_no_offer_found(self):
        """Test that command logs no offer needs to be changed."""
        with LogCapture(LOGGER_NAME) as log:
            call_command('change_priority_of_offers')
            log.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'No offer found which needs a priority fix'
                )
            )

    @ddt.data(True, False)
    def test_change_priority_of_offers(self, yes_no_value):
        """Test that command changes priority of voucher offers."""
        factories.ConditionalOfferFactory(offer_type=ConditionalOffer.SITE)
        factories.ConditionalOfferFactory(name='Coupon ENT Offer', offer_type=ConditionalOffer.VOUCHER, priority=20)
        ent_offer_count = 2
        for idx in range(ent_offer_count):
            factories.ConditionalOfferFactory(
                name='ENT Offer {}'.format(idx), offer_type=ConditionalOffer.VOUCHER, priority=5
            )

        offer_names = '1. ENT Offer 0\n2. ENT Offer 1'
        expected = [
            (
                LOGGER_NAME,
                'WARNING',
                'Conditional offers to be updated\n{offer_names}'.format(
                    offer_names=offer_names,
                )
            )
        ]

        with patch(self.YES_NO_PATCH_LOCATION) as mocked_yes_no:
            mocked_yes_no.return_value = yes_no_value
            with LogCapture(LOGGER_NAME) as log:
                call_command('change_priority_of_offers')
                if yes_no_value:
                    log_msg = 'Operation completed. {} conditional offers updated successfully.'.format(ent_offer_count)
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

    @ddt.data(
        (0, 10, 5),
        (10, 20, 10),
        (20, 25, 15),
    )
    @ddt.unpack
    def test_change_priority_of_offers_in_batches(self, offset, limit, priority):
        """Test that command changes priority of voucher offers in batches."""
        ent_offer_count = 30
        for idx in range(ent_offer_count):
            factories.ConditionalOfferFactory(
                name='ENT Offer {}'.format(idx), offer_type=ConditionalOffer.VOUCHER, priority=priority
            )

        update_offer_cnt = limit if offset + limit <= ent_offer_count else ent_offer_count - offset
        offers_list = [
            '{}. ENT Offer {}'.format(idx + 1, val) for idx, val in enumerate(range(offset, offset + update_offer_cnt))
        ]
        offer_names = '\n'.join(offers_list)
        expected = [
            (
                LOGGER_NAME,
                'WARNING',
                'Conditional offers to be updated\n{offer_names}'.format(
                    offer_names=offer_names,
                )
            )
        ]

        with patch(self.YES_NO_PATCH_LOCATION) as mocked_yes_no:
            mocked_yes_no.return_value = True
            with LogCapture(LOGGER_NAME) as log:
                call_command('change_priority_of_offers', offset=offset, limit=limit, priority=priority)
                log_msg = 'Operation completed. {} conditional offers updated successfully.'.format(update_offer_cnt)
                expected.append(
                    (
                        LOGGER_NAME,
                        'INFO',
                        log_msg
                    )
                )
                log.check(*expected)

    def test_change_priority_of_offers_with_exception(self):
        """Test that command with exception."""
        expected = [
            (
                LOGGER_NAME,
                'ERROR',
                'Command execution failed while executing batch -1,10\nNegative indexing is not supported.'
            )
        ]

        with patch(self.YES_NO_PATCH_LOCATION) as mocked_yes_no:
            mocked_yes_no.return_value = True
            with LogCapture(LOGGER_NAME) as log:
                call_command('change_priority_of_offers', offset=-1, limit=10)
                log.check(*expected)
