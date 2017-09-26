import datetime

import ddt
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from oscar.core.loading import get_model

from ecommerce.tests.testcases import TestCase

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
