from __future__ import unicode_literals
from StringIO import StringIO

from django.core.management import call_command
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.tests.testcases import TestCase

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Voucher = get_model('voucher', 'Voucher')


class SetMaxApplicationsToNoneCommandTest(TestCase):
    command = 'set_max_applications_to_none'
    filter_condition = {
        'max_global_applications': 1,
        'vouchers__usage': Voucher.SINGLE_USE
    }

    def call_command_and_return_output(self):
        output = StringIO()
        call_command(self.command, stdout=output)
        return output

    def test_command_on_one_sample(self):
        """Verify the command changes single use vouchers offer with max_global_applications value set to one."""
        offer = factories.ConditionalOfferFactory(max_global_applications=1)
        voucher = factories.VoucherFactory(usage=Voucher.SINGLE_USE)
        voucher.offers.add(offer)
        self.assertEqual(ConditionalOffer.objects.filter(**self.filter_condition).count(), 1)

        output = self.call_command_and_return_output()
        actual_output = output.getvalue().strip()

        self.assertTrue(actual_output.startswith(
            'Setting max_global_applications field to None for ConditionalOffer [{}]...'.format(offer)
        ))
        self.assertTrue(actual_output.endswith('Done.'))
        self.assertEqual(ConditionalOffer.objects.filter(**self.filter_condition).count(), 0)

    def test_command_without_sample(self):
        """Verify the command is only showing a message when no queryset is found."""
        self.assertEqual(ConditionalOffer.objects.filter(**self.filter_condition).count(), 0)
        output = self.call_command_and_return_output()
        self.assertEqual('Nothing to do here.', output.getvalue().strip())
        self.assertEqual(ConditionalOffer.objects.filter(**self.filter_condition).count(), 0)

    def test_command_only_target_single_use_vouchers(self):
        """Verify the command doesn't target multi-use vouchers."""
        offer = factories.ConditionalOfferFactory(max_global_applications=1)
        voucher = factories.VoucherFactory(usage=Voucher.MULTI_USE)
        voucher.offers.add(offer)
        output = self.call_command_and_return_output()
        self.assertEqual('Nothing to do here.', output.getvalue().strip())
        unaffected_offer = ConditionalOffer.objects.get(id=offer.id)
        self.assertEqual(unaffected_offer.max_global_applications, 1)
        self.assertEqual(unaffected_offer.vouchers.first().usage, Voucher.MULTI_USE)
