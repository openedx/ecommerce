from decimal import Decimal

import ddt
import mock
from django.conf import settings
from oscar.core.loading import get_model

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.checkout.utils import add_currency
from ecommerce.extensions.offer.utils import (
    _remove_exponent_and_trailing_zeros,
    format_benefit_value,
    send_assigned_offer_email,
    send_assigned_offer_reminder_email
)
from ecommerce.extensions.test.factories import *  # pylint:disable=wildcard-import,unused-wildcard-import
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')


@ddt.ddt
class UtilTests(DiscoveryTestMixin, TestCase):

    def setUp(self):
        super(UtilTests, self).setUp()
        self.course = CourseFactory(partner=self.partner)
        self.verified_seat = self.course.create_or_update_seat('verified', False, 100)
        self.stock_record = StockRecord.objects.filter(product=self.verified_seat).first()
        self.seat_price = self.stock_record.price_excl_tax
        self._range = RangeFactory(products=[self.verified_seat, ])

        self.percentage_benefit = BenefitFactory(type=Benefit.PERCENTAGE, range=self._range, value=35.00)
        self.value_benefit = BenefitFactory(type=Benefit.FIXED, range=self._range, value=self.seat_price - 10)

    def test_format_benefit_value(self):
        """ format_benefit_value(benefit) should format benefit value based on benefit type """
        benefit_value = format_benefit_value(self.percentage_benefit)
        self.assertEqual(benefit_value, '35%')

        benefit_value = format_benefit_value(self.value_benefit)
        expected_benefit = add_currency(Decimal((self.seat_price - 10)))
        self.assertEqual(benefit_value, '${expected_benefit}'.format(expected_benefit=expected_benefit))

    def test_format_program_benefit_value(self):
        """ format_benefit_value(program_benefit) should format benefit value based on proxy class. """
        percentage_benefit = PercentageDiscountBenefitWithoutRangeFactory()
        benefit_value = format_benefit_value(percentage_benefit)
        self.assertEqual(benefit_value, '{}%'.format(percentage_benefit.value))

        absolute_benefit = AbsoluteDiscountBenefitWithoutRangeFactory()
        benefit_value = format_benefit_value(absolute_benefit)
        expected_value = add_currency(Decimal(absolute_benefit.value))
        self.assertEqual(benefit_value, '${}'.format(expected_value))

    @ddt.data(
        ('1.0', '1'),
        ('5000.0', '5000'),
        ('1.45000', '1.45'),
        ('5000.40000', '5000.4'),
    )
    @ddt.unpack
    def test_remove_exponent_and_trailing_zeros(self, value, expected):
        """
        _remove_exponent_and_trailing_zeros(decimal) should remove exponent and trailing zeros
        from decimal number
        """
        decimal = _remove_exponent_and_trailing_zeros(Decimal(value))
        self.assertEqual(decimal, Decimal(expected))

    @mock.patch('ecommerce.extensions.offer.utils.send_offer_assignment_email')
    @ddt.data(
        (
            {
                'offer_assignment_id': 555,
                'learner_email': 'johndoe@unknown.com',
                'code': 'GIL7RUEOU7VHBH7Q',
                'redemptions_remaining': 10,
                'code_expiration_date': '2018-12-19'
            },
            None,
        ),
    )
    @ddt.unpack
    def test_send_assigned_offer_email(
            self,
            tokens,
            side_effect,
            mock_sailthru_task,
    ):
        """ Test that the offer assignment email message is correctly formatted with correct call to async task. """
        email_subject = settings.OFFER_ASSIGNMENT_EMAIL_DEFAULT_SUBJECT
        mock_sailthru_task.delay.side_effect = side_effect
        template = settings.OFFER_ASSIGNMENT_EMAIL_DEFAULT_TEMPLATE
        send_assigned_offer_email(
            template,
            tokens.get('offer_assignment_id'),
            tokens.get('learner_email'),
            tokens.get('code'),
            tokens.get('redemptions_remaining'),
            tokens.get('code_expiration_date'),
        )
        expected_email_body = template.format(
            REDEMPTIONS_REMAINING=tokens.get('redemptions_remaining'),
            USER_EMAIL=tokens.get('learner_email'),
            CODE=tokens.get('code'),
            EXPIRATION_DATE=tokens.get('code_expiration_date')
        )
        mock_sailthru_task.delay.assert_called_once_with(
            tokens.get('learner_email'),
            tokens.get('offer_assignment_id'),
            email_subject, expected_email_body)

    @mock.patch('ecommerce.extensions.offer.utils.send_offer_update_email')
    @ddt.data(
        (
            {
                'learner_email': 'johndoe@unknown.com',
                'code': 'GIL7RUEOU7VHBH7Q',
                'redeemed_offer_count': 0,
                'total_offer_count': 1,
                'code_expiration_date': '2018-12-19'
            },
            None,
        ),
    )
    @ddt.unpack
    def test_send_assigned_offer_reminder_email(
            self,
            tokens,
            side_effect,
            mock_sailthru_task,
    ):
        """ Test that the offer assignment reminder email message is correctly formatted
         with correct call to the async task in ecommerce-worker.
        """
        email_subject = settings.OFFER_ASSIGNMENT_EMAIL_REMINDER_DEFAULT_SUBJECT
        mock_sailthru_task.delay.side_effect = side_effect
        template = settings.OFFER_ASSIGNMENT_EMAIL_REMINDER_DEFAULT_TEMPLATE
        send_assigned_offer_reminder_email(
            template,
            tokens.get('learner_email'),
            tokens.get('code'),
            tokens.get('redeemed_offer_count'),
            tokens.get('total_offer_count'),
            tokens.get('code_expiration_date'),
        )
        expected_email_body = template.format(
            REDEEMED_OFFER_COUNT=tokens.get('redeemed_offer_count'),
            TOTAL_OFFER_COUNT=tokens.get('total_offer_count'),
            USER_EMAIL=tokens.get('learner_email'),
            CODE=tokens.get('code'),
            EXPIRATION_DATE=tokens.get('code_expiration_date')
        )
        mock_sailthru_task.delay.assert_called_once_with(
            tokens.get('learner_email'),
            email_subject,
            expected_email_body
        )
