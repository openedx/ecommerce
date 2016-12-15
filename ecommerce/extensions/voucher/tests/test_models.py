import datetime

from django.core.exceptions import ValidationError
from django.utils.timezone import now
from oscar.core.loading import get_model

from ecommerce.tests.testcases import TestCase

Voucher = get_model('voucher', 'Voucher')


class VoucherTests(TestCase):
    def test_create_voucher(self):
        """ Verify voucher is created. """
        data = {
            'code': 'TESTCODE',
            'start_datetime': str(now() - datetime.timedelta(days=1)),
            'end_datetime': str(now() + datetime.timedelta(days=1))
        }
        voucher = Voucher.objects.create(**data)
        self.assertEqual(voucher.code, data['code'])
        self.assertEqual(voucher.start_datetime, data['start_datetime'])
        self.assertEqual(voucher.end_datetime, data['end_datetime'])

    def test_no_code_raises_exception(self):
        """ Verify creating voucher without code set raises exception. """
        with self.assertRaises(ValidationError):
            Voucher.objects.create()

    def test_wrong_code_data_raises_exception(self):
        """ Verify creating voucher with code value that contains spaces (non alphanumeric value) raises exception. """
        with self.assertRaises(ValidationError):
            Voucher.objects.create(code='Only alphanumeric without spaces')
