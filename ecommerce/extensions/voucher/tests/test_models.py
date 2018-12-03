import datetime

import ddt
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from oscar.core.loading import get_model
from oscar.test.factories import UserFactory
from waffle.models import Switch
from ecommerce.enterprise.constants import ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH
from ecommerce.extensions.test import factories

from ecommerce.tests.testcases import TestCase

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Voucher = get_model('voucher', 'Voucher')


@ddt.ddt
class VoucherTests(TestCase):
    def setUp(self):
        super(VoucherTests, self).setUp()
        self.data = {
            'code': 'TESTCODE',
            'end_datetime': now() + datetime.timedelta(days=1),
            'start_datetime': now() - datetime.timedelta(days=1)
        }

    def test_create_voucher(self):
        """ Verify voucher is created. """
        voucher = Voucher.objects.create(**self.data)
        self.assertEqual(voucher.code, self.data['code'])
        self.assertEqual(voucher.start_datetime, self.data['start_datetime'])
        self.assertEqual(voucher.end_datetime, self.data['end_datetime'])

    def test_no_code_raises_exception(self):
        """ Verify creating voucher without code set raises exception. """
        del self.data['code']
        with self.assertRaises(ValidationError):
            Voucher.objects.create(**self.data)

    def test_wrong_code_data_raises_exception(self):
        """ Verify creating voucher with code value that contains spaces (non alphanumeric value) raises exception. """
        self.data['code'] = 'Only alphanumeric without spaces'
        with self.assertRaises(ValidationError):
            Voucher.objects.create(**self.data)

    @ddt.data('end_datetime', 'start_datetime')
    def test_no_datetime_set_raises_exception(self, key):
        """ Verify creating voucher without start/end datetime set raises exception. """
        del self.data[key]
        with self.assertRaises(ValidationError):
            Voucher.objects.create(**self.data)

    @ddt.data('end_datetime', 'start_datetime')
    def test_incorrect_datetime_value_raises_exception(self, key):
        """ Verify creating voucher with incorrect start/end datetime value raises exception. """
        self.data[key] = 'incorrect value'
        with self.assertRaises(ValidationError):
            Voucher.objects.create(**self.data)

    def test_start_datetime_after_end_datetime(self):
        """ Verify creating voucher with start datetime set after end datetime raises exception. """
        self.data['start_datetime'] = self.data['end_datetime'] + datetime.timedelta(days=1)
        with self.assertRaises(ValidationError):
            Voucher.objects.create(**self.data)

    def test_best_offer(self):
        voucher = Voucher.objects.create(**self.data)
        first_offer = factories.ConditionalOfferFactory()
        voucher.offers.add(first_offer)
        # Test that with the switch off, the offer gets returned.
        Switch.objects.update_or_create(name=ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH, defaults={'active': False})
        assert voucher.best_offer == first_offer
        # Test that with the switch on, the same offer gets returned.
        Switch.objects.update_or_create(name=ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH, defaults={'active': True})
        assert voucher.best_offer == first_offer
        # Now add a second enterprise offer, and see that with the switch on, the enterprise offer gets returned.
        second_offer = factories.EnterpriseOfferFactory()
        voucher.offers.add(second_offer)
        assert voucher.best_offer == second_offer
        # Add a third enterprise offer, and see that the first enterprise offer gets returned
        # because of multiple enterprise offers being available.
        third_offer = factories.EnterpriseOfferFactory()
        voucher.offers.add(third_offer)
        assert voucher.best_offer == second_offer
        # Turn the switch off and see that the oldest offer gets returned.
        Switch.objects.update_or_create(name=ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH, defaults={'active': False})
        assert voucher.best_offer == first_offer

    def test_create_voucher_with_multi_use_per_customer_usage(self):
        """ Verify voucher is created with `MULTI_USE_PER_CUSTOMER` usage type. """
        voucher_data = dict(self.data, usage=Voucher.MULTI_USE_PER_CUSTOMER)
        voucher = Voucher.objects.create(**voucher_data)
        user = UserFactory()
        self.assertEqual(voucher.usage, Voucher.MULTI_USE_PER_CUSTOMER)
        is_available, message = voucher.is_available_to_user(user)
        self.assertTrue(is_available)
        self.assertEqual(message, '')
