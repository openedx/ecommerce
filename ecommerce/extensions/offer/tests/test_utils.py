

from decimal import Decimal

import ddt
import mock
from django.conf import settings
from oscar.core.loading import get_model
from oscar.test.factories import StockRecord
from waffle.models import Switch

from ecommerce.core.constants import ENABLE_BRAZE
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.checkout.utils import add_currency
from ecommerce.extensions.offer.utils import (
    SafeDict,
    _remove_exponent_and_trailing_zeros,
    format_assigned_offer_email,
    format_benefit_value,
    format_email,
    send_assigned_offer_email,
    send_assigned_offer_reminder_email,
    send_revoked_offer_email
)
from ecommerce.extensions.test.factories import (
    AbsoluteDiscountBenefitWithoutRangeFactory,
    BenefitFactory,
    PercentageDiscountBenefitWithoutRangeFactory,
    RangeFactory
)
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')


@ddt.ddt
class UtilTests(DiscoveryTestMixin, TestCase):
    _BROKEN_EMAIL_TEMPLATE = '''
        Text
        {DOES_NOT_EXIST} {USER_EMAIL}
        code: {CODE} {CODE}
        {}
        { abc d }
        More text.
        '''

    def setUp(self):
        super(UtilTests, self).setUp()
        self.course = CourseFactory(partner=self.partner)
        self.verified_seat = self.course.create_or_update_seat('verified', False, 100)
        self.stock_record = StockRecord.objects.filter(product=self.verified_seat).first()
        self.seat_price = self.stock_record.price
        self._range = RangeFactory(products=[self.verified_seat, ])

        self.percentage_benefit = BenefitFactory(type=Benefit.PERCENTAGE, range=self._range, value=35.00)
        self.value_benefit = BenefitFactory(type=Benefit.FIXED, range=self._range, value=self.seat_price - 10)
        self.assertEqual.__self__.maxDiff = None

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
            'subject',
            'hi',
            'bye',
            [{'name': 'abc.png', 'url': 'https://www.example.com'},
             {'name': 'def.png', 'url': 'https://www.example.com'}],
            {
                'offer_assignment_id': 555,
                'learner_email': 'johndoe@unknown.com',
                'code': 'GIL7RUEOU7VHBH7Q',
                'redemptions_remaining': 10,
                'code_expiration_date': '2018-12-19'
            },
            None,
            'sender alias',
            'edx@example.com',
            ''
        ),
        (
            'subject',
            'hi',
            'bye',
            [{'name': 'abc.png', 'url': 'https://www.example.com'},
             {'name': 'def.png', 'url': 'https://www.example.com'}],
            {
                'offer_assignment_id': 555,
                'learner_email': 'johndoe@unknown.com',
                'code': 'GIL7RUEOU7VHBH7Q',
                'redemptions_remaining': 10,
                'code_expiration_date': '2018-12-19'
            },
            None,
            'sender alias',
            'edx@example.com',
            'https://bears.party'
        ),
    )
    @ddt.unpack
    def test_send_assigned_offer_email(
            self,
            subject,
            greeting,
            closing,
            attachments,
            tokens,
            side_effect,
            sender_alias,
            reply_to,
            base_enterprise_url,
            mock_email_task,
    ):
        """ Test that the offer assignment email message is sent to async task. """
        mock_email_task.delay.side_effect = side_effect
        send_assigned_offer_email(
            subject,
            greeting,
            closing,
            tokens.get('offer_assignment_id'),
            tokens.get('learner_email'),
            tokens.get('code'),
            tokens.get('redemptions_remaining'),
            tokens.get('code_expiration_date'),
            sender_alias,
            reply_to,
            base_enterprise_url,
            attachments,
        )
        mock_email_task.delay.assert_called_once_with(
            tokens.get('learner_email'),
            tokens.get('offer_assignment_id'),
            subject,
            mock.ANY,
            sender_alias,
            reply_to,
            base_enterprise_url=base_enterprise_url,
            attachments=attachments,
        )

    @mock.patch('ecommerce.extensions.offer.utils.send_offer_assignment_email')
    @ddt.data(
        (
            'subject',
            'hi',
            'bye',
            [{'name': 'abc.png', 'url': 'https://www.example.com'},
             {'name': 'def.png', 'url': 'https://www.example.com'}],
            {
                'offer_assignment_id': 555,
                'learner_email': 'johndoe@unknown.com',
                'code': 'GIL7RUEOU7VHBH7Q',
                'redemptions_remaining': 10,
                'code_expiration_date': '2018-12-19'
            },
            None,
            'sender alias',
            'edx@example.com',
            '',
            'https://www.edx.org'
        ),
        (
            'subject',
            'hi',
            'bye',
            [{'name': 'abc.png', 'url': 'https://www.example.com'},
             {'name': 'def.png', 'url': 'https://www.example.com'}],
            {
                'offer_assignment_id': 555,
                'learner_email': 'johndoe@unknown.com',
                'code': 'GIL7RUEOU7VHBH7Q',
                'redemptions_remaining': 10,
                'code_expiration_date': '2018-12-19'
            },
            None,
            'sender alias',
            'edx@example.com',
            'https://bears.party',
            'https://bears.party'
        ),
    )
    @ddt.unpack
    def test_send_assigned_offer_email_via_braze(
            self,
            subject,
            greeting,
            closing,
            attachments,
            tokens,
            side_effect,
            sender_alias,
            reply_to,
            base_enterprise_url,
            search_url,
            mock_email_task,
    ):
        """ Test that the offer assignment email message is sent to async task. """
        switch, __ = Switch.objects.get_or_create(name=ENABLE_BRAZE)
        switch.active = True
        switch.save()
        mock_email_task.delay.side_effect = side_effect
        send_assigned_offer_email(
            subject,
            greeting,
            closing,
            tokens.get('offer_assignment_id'),
            tokens.get('learner_email'),
            tokens.get('code'),
            tokens.get('redemptions_remaining'),
            tokens.get('code_expiration_date'),
            sender_alias,
            reply_to,
            base_enterprise_url,
            attachments
        )
        email_body = format_assigned_offer_email(
            greeting,
            closing,
            tokens.get('learner_email'),
            tokens.get('code'),
            tokens.get('redemptions_remaining'),
            tokens.get('code_expiration_date'),
            search_url
        )
        mock_email_task.delay.assert_called_once_with(
            tokens.get('learner_email'),
            tokens.get('offer_assignment_id'),
            subject,
            email_body,
            sender_alias,
            reply_to,
            base_enterprise_url=base_enterprise_url,
            attachments=attachments,
        )

    @mock.patch('ecommerce.extensions.offer.utils.send_offer_assignment_email')
    def test_send_assigned_offer_email_without_base_ent_url_and_attachments(self, mock_email_task):
        send_assigned_offer_email(
            "You have mail",
            "you",
            "KTHXBAI",
            42,
            "bears@bearparty.com",
            'BearsOnly',
            1,
            '2020-12-19',
            'sender alias',
            'edx@example.com',
        )

        mock_email_task.delay.assert_called_once_with(
            "bears@bearparty.com",
            42,
            "You have mail",
            mock.ANY,
            'sender alias',
            'edx@example.com',
            attachments=[],
            base_enterprise_url=''
        )

    @mock.patch('ecommerce.extensions.offer.utils.send_offer_update_email')
    @ddt.data(
        (
            'subject',
            'hi',
            'bye',
            [{'name': 'abc.png', 'url': 'https://www.example.com'},
             {'name': 'def.png', 'url': 'https://www.example.com'}],
            'sender_alias',
            'edx@example.com',
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
            subject,
            greeting,
            closing,
            attachments,
            sender_alias,
            reply_to,
            tokens,
            side_effect,
            mock_email_task,
    ):
        """
        Test that the offer assignment reminder email message is sent to the async task in ecommerce-worker.
        """
        mock_email_task.delay.side_effect = side_effect
        send_assigned_offer_reminder_email(
            subject,
            greeting,
            closing,
            tokens.get('learner_email'),
            tokens.get('code'),
            tokens.get('redeemed_offer_count'),
            tokens.get('total_offer_count'),
            tokens.get('code_expiration_date'),
            sender_alias,
            reply_to,
            attachments=attachments
        )
        mock_email_task.delay.assert_called_once_with(
            tokens.get('learner_email'),
            subject,
            mock.ANY,
            sender_alias,
            reply_to,
            # base_enterprise_url should be blank as it was not passed in
            base_enterprise_url='',
            attachments=attachments,
        )

    @mock.patch('ecommerce.extensions.offer.utils.send_offer_update_email')
    @ddt.data(
        (
            'subject',
            'hi',
            'bye',
            [{'name': 'abc.png', 'url': 'https://www.example.com'},
             {'name': 'def.png', 'url': 'https://www.example.com'}],
            'sender_alias',
            'edx@example.com',
            {
                'learner_email': 'johndoe@unknown.com',
                'code': 'GIL7RUEOU7VHBH7Q',
                'redeemed_offer_count': 0,
                'total_offer_count': 1,
                'code_expiration_date': '2018-12-19',
                'base_enterprise_url': 'http://mylearnerportal.com'
            },
            None,
        ),
    )
    @ddt.unpack
    def test_send_assigned_offer_reminder_email_with_base_url(
            self,
            subject,
            greeting,
            closing,
            attachments,
            sender_alias,
            reply_to,
            tokens,
            side_effect,
            mock_email_task,
    ):
        """
        Test that the offer assignment reminder email message is sent to the async task in ecommerce-worker.
        """
        mock_email_task.delay.side_effect = side_effect
        send_assigned_offer_reminder_email(
            subject,
            greeting,
            closing,
            tokens.get('learner_email'),
            tokens.get('code'),
            tokens.get('redeemed_offer_count'),
            tokens.get('total_offer_count'),
            tokens.get('code_expiration_date'),
            sender_alias,
            reply_to,
            attachments,
            tokens.get('base_enterprise_url'),
        )
        mock_email_task.delay.assert_called_once_with(
            tokens.get('learner_email'),
            subject,
            mock.ANY,
            sender_alias,
            reply_to,
            base_enterprise_url=tokens.get('base_enterprise_url'),
            attachments=attachments
        )

    @mock.patch('ecommerce.extensions.offer.utils.send_offer_update_email')
    @ddt.data(
        (
            'subject',
            'hi',
            'bye',
            [{'name': 'abc.png', 'url': 'https://www.example.com'},
             {'name': 'def.png', 'url': 'https://www.example.com'}],
            'sender_alias',
            'edx@example.com',
            {
                'learner_email': 'johndoe@unknown.com',
                'code': 'GIL7RUEOU7VHBH7Q',
            },
            'https://bears.party',
            None,
        ),
    )
    @ddt.unpack
    def test_send_offer_revoked_email(
            self,
            subject,
            greeting,
            closing,
            attachments,
            sender_alias,
            reply_to,
            tokens,
            base_enterprise_url,
            side_effect,
            mock_email_task,
    ):
        """
        Test that the offer revocation email message is sent to the async task in ecommerce-worker.
        """
        mock_email_task.delay.side_effect = side_effect
        send_revoked_offer_email(
            subject,
            greeting,
            closing,
            tokens.get('learner_email'),
            tokens.get('code'),
            sender_alias,
            reply_to,
            base_enterprise_url,
            attachments,
        )
        mock_email_task.delay.assert_called_once_with(
            tokens.get('learner_email'),
            subject,
            mock.ANY,
            sender_alias,
            reply_to,
            attachments=attachments,
        )

    @ddt.data(
        (
            settings.OFFER_ASSIGNMENT_EMAIL_TEMPLATE,
            'hi ',
            'bye ',
            {
                'learner_email': 'johndoe@unknown.com',
                'code': 'GIL7RUEOU7VHBH7Q',
                'redemptions_remaining': 500,
                'code_expiration_date': '2018-12-19'
            },
        ),
    )
    @ddt.unpack
    def test_format_assigned_offer_email(
            self,
            template,
            greeting,
            closing,
            tokens,
    ):
        """
        Test that the assigned offer email message is formatted correctly.
        """
        placeholder_dict = SafeDict(
            REDEMPTIONS_REMAINING=tokens.get('redemptions_remaining'),
            USER_EMAIL=tokens.get('learner_email'),
            CODE=tokens.get('code'),
            EXPIRATION_DATE=tokens.get('code_expiration_date'),
        )
        email = format_email(template, placeholder_dict, greeting, closing)
        self.assertIn(str(tokens.get('redemptions_remaining')), email)
        self.assertIn(tokens.get('learner_email'), email)
        self.assertIn(tokens.get('code'), email)
        self.assertIn(tokens.get('code_expiration_date'), email)
        self.assertIn(greeting, email)
        self.assertIn(closing, email)

    def test_format_assigned_offer_broken_email(self):
        """
        Test that the assigned offer email message is formatted correctly if the template is broken.
        """
        greeting = 'hi {CODE} <h1>there</h1>\n'
        closing = '\nbye {CODE}, <h3>come back soon!</h3>'
        code = 'GIL7RUEOU7VHBH7Q'
        placeholder_dict = SafeDict(
            REDEMPTIONS_REMAINING=500,
            USER_EMAIL='johndoe@unknown.com',
            CODE=code,
            EXPIRATION_DATE='2018-12-19',
        )
        email = format_email(self._BROKEN_EMAIL_TEMPLATE, placeholder_dict, greeting, closing)
        self.assertIn('{DOES_NOT_EXIST}', email)
        self.assertIn(code, email)

        # Compare strings, ignoring whitespace differences
        expected_email = """
            hi {CODE} &lt;h1&gt;there&lt;/h1&gt;<br/><br/>
            Text<br/>
            {DOES_NOT_EXIST} johndoe@unknown.com<br/>
            code: GIL7RUEOU7VHBH7Q GIL7RUEOU7VHBH7Q<br/>
            {}<br/>
            { abc d }<br/>
            More text.<br/> <br/>bye {CODE}, &lt;h3&gt;come back soon!&lt;/h3&gt;
            """
        self.assertEqual(email.split(), expected_email.split())

    def test_format_assigned_offer_no_greeting(self):
        """
        Test that the assigned offer email message is formatted correctly if there is no greeting or closing.
        """
        code = 'ABC7RUEOU7VHBH7Q'
        placeholder_dict = SafeDict(
            REDEMPTIONS_REMAINING=499,
            USER_EMAIL='johndoe2@unknown.com',
            CODE=code,
            EXPIRATION_DATE='2018-12-19',
        )
        email = format_email(self._BROKEN_EMAIL_TEMPLATE, placeholder_dict, None, None)
        self.assertIn('{DOES_NOT_EXIST}', email)
        self.assertIn(code, email)

        # Compare strings, ignoring whitespace differences
        expected_email = """
            <br/> Text<br/>
            {DOES_NOT_EXIST} johndoe2@unknown.com<br/>
            code: ABC7RUEOU7VHBH7Q ABC7RUEOU7VHBH7Q<br/>
            {}<br/>
            { abc d }<br/>
            More text.<br/>
            """
        self.assertEqual(email.split(), expected_email.split())
