from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ecommerce.extensions.voucher.models import Voucher
from ecommerce.extensions.voucher.tasks import update_voucher_names


class ManagementCommandTests(TestCase):
    def setUp(self):
        self.data = {
            'name': 'Test voucher',
            'code': 'TESTCODE',
            'start_datetime': timezone.now(),
            'end_datetime': timezone.now() + timedelta(days=7)
        }
        voucher = Voucher.objects.create(**self.data)

    @mock.patch('ecommerce.extensions.voucher.tasks.update_voucher_names.delay')
    def test_update_voucher_names_command(self, mock_delay):

        call_command('update_voucher_names')
        # Assert that the Celery task is scheduled
        self.assertTrue(mock_delay.called)

    @mock.patch('ecommerce.extensions.voucher.models.Voucher.objects.all')
    def test_update_voucher_names_task(self, mock_all):
        # Mock Voucher objects
        start_datetime = timezone.now()
        end_datetime = timezone.now() + timedelta(days=7)

        mock_vouchers =
        [
            Voucher(id=1, name='Name1', code='SASAFR',
                    start_datetime=start_datetime, end_datetime=start_datetime),
            Voucher(id=2, name='Name2', code='EWRRFEC',
                    start_datetime=start_datetime, end_datetime=end_datetime),
        ]
        mock_all.return_value = mock_vouchers

        # Call the Celery task
        update_voucher_names(mock_vouchers)
        # Assert that the names are updated as expected
        self.assertEqual(mock_vouchers[0].name, '1 - Name1')
        self.assertEqual(mock_vouchers[1].name, '2 - Name2')

    @mock.patch('ecommerce.extensions.voucher.tasks.update_voucher_names.delay')
    def test_voucher_name_update_once(self, mock_delay):
        original_name = 'Original Name'
        code = 'ABC123XSD'
        start_datetime = timezone.now()
        end_datetime = start_datetime + timedelta(days=7)
        voucher = Voucher.objects.create(name=original_name,
                                         code=code,
                                         start_datetime=start_datetime,
                                         end_datetime=end_datetime
                                         )

        call_command('update_voucher_names')
        call_command('update_voucher_names')

        updated_voucher = Voucher.objects.get(id=voucher.id)

        self.assertEqual(mock_delay.call_count, 2)
        self.assertEqual(updated_voucher.name, f"{voucher.id} - {original_name}")
