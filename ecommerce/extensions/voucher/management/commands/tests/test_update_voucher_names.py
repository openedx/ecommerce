from datetime import timedelta
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from ecommerce.extensions.voucher.models import Voucher
from ecommerce.extensions.voucher.tasks import update_voucher_names


class ManagementCommandTests(TestCase):
    def setUp(self):
        self.voucher_name = 'Test voucher'
        self.data = {
            'name': self.voucher_name,
            'start_datetime': timezone.now(),
            'end_datetime': timezone.now() + timedelta(days=7)
        }
        for item in range(3):
            code = 'TESTCODE' + str(item)
            Voucher.objects.create(code=code, **self.data)

    @mock.patch('ecommerce.extensions.voucher.tasks.update_voucher_names.delay')
    def test_update_voucher_names_command(self, mock_delay):
        """
        Verify a celery task is spun off when the management command is run.
        """
        call_command('update_voucher_names', batch_size=1)

        assert mock_delay.called is True
        assert mock_delay.call_count == 3

    def test_update_voucher_names_task(self):
        """
        Verify task called in management command updates the voucher names correctly.
        """
        call_command('update_voucher_names')

        for voucher_id in [1, 2, 3]:
            voucher = Voucher.objects.get(id=voucher_id)
            assert voucher.name == f'{voucher_id} - {self.voucher_name}'

    def test_voucher_name_update_idempotent(self):
        """
        Verify running the management command multiple times ultimately results
        in the same voucher names.
        """
        # Before we run the command
        for voucher_id in [1, 2, 3]:
            voucher = Voucher.objects.get(id=voucher_id)
            assert voucher.name == self.voucher_name

        # And after each time we run the command
        for _ in range(2):
            call_command('update_voucher_names')

            for voucher_id in [1, 2, 3]:
                voucher = Voucher.objects.get(id=voucher_id)
                assert voucher.name == f'{voucher_id} - {self.voucher_name}'
