# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

import six
from django.core.exceptions import ValidationError
from testfixtures import LogCapture

from ecommerce.extensions.payment.models import EnterpriseContractMetadata, SDNCheckFailure, SDNFallbackMetadata
from ecommerce.tests.testcases import TestCase


class SDNCheckFailureTests(TestCase):
    def setUp(self):
        super(SDNCheckFailureTests, self).setUp()
        self.full_name = 'Keyser Söze'
        self.username = 'UnusualSuspect'
        self.country = 'US'
        self.sdn_check_response = {'description': 'Looks a bit suspicious.'}

    def test_unicode(self):
        """ Verify the __unicode__ method returns the correct value. """
        basket = SDNCheckFailure.objects.create(
            full_name=self.full_name,
            username=self.username,
            country=self.country,
            site=self.site,
            sdn_check_response=self.sdn_check_response
        )
        expected = 'SDN check failure [{username}]'.format(
            username=self.username
        )

        self.assertEqual(six.text_type(basket), expected)


class EnterpriseContractMetadataTests(TestCase):
    def setUp(self):
        super(EnterpriseContractMetadataTests, self).setUp()
        self.ecm = EnterpriseContractMetadata()

    def test_validate_fixed_value_good(self):
        """
        Verify expected good values do not throw errors on clean.
        """
        self.ecm.discount_type = EnterpriseContractMetadata.FIXED
        good_values = [
            '1234567890',
            '1234567890.23',
            '10000',
            '.45',
        ]
        for value in good_values:
            self.ecm.discount_value = value
            self.ecm.clean()

    def test_validate_fixed_value_bad(self):
        """
        Verify expected bad values throw errors on clean.
        """
        self.ecm.discount_type = EnterpriseContractMetadata.FIXED
        bad_values = [
            '12345678901',
            '12345678901.23',
            '.2345',
            '123.456',

        ]
        for value in bad_values:
            self.ecm.discount_value = value
            with self.assertRaises(ValidationError):
                self.ecm.clean()

    def test_validate_percentage_value_good(self):
        """
        Verify expected good values do not throw errors on clean.
        """
        self.ecm.discount_type = EnterpriseContractMetadata.PERCENTAGE
        good_values = [
            '10.12345',
            '95',
            '12.1',
            '100',
            '100.00000',
        ]
        for value in good_values:
            self.ecm.discount_value = value
            self.ecm.clean()

    def test_validate_percentage_value_bad(self):
        """
        Verify expected bad values throw errors on clean.
        """
        self.ecm.discount_type = EnterpriseContractMetadata.PERCENTAGE
        bad_values = [
            '145123',
            '100.01',
        ]
        for value in bad_values:
            self.ecm.discount_value = value
            with self.assertRaises(ValidationError):
                self.ecm.clean()


class SDNFallbackMetadataTests(TestCase):
    LOGGER_NAME = 'ecommerce.extensions.payment.models'

    def setUp(self):
        super(SDNFallbackMetadataTests, self).setUp()
        self.file_checksum = 'foobar'
        self.download_timestamp = datetime.now() - timedelta(days=1)

    def test_minimum_requirements(self):
        """Make sure the row is created correctly with the minimum dataset + defaults."""
        new_metadata = SDNFallbackMetadata(
            file_checksum=self.file_checksum,
            download_timestamp=self.download_timestamp,
        )
        new_metadata.full_clean()
        new_metadata.save()

        self.assertEqual(len(SDNFallbackMetadata.objects.all()), 1)

        actual_metadata = SDNFallbackMetadata.objects.all()[0]
        self.assertEqual(actual_metadata.file_checksum, self.file_checksum)
        self.assertIsInstance(actual_metadata.download_timestamp, datetime)
        self.assertEqual(actual_metadata.import_timestamp, None)
        self.assertEqual(actual_metadata.import_state, 'New')
        self.assertIsInstance(actual_metadata.created, datetime)
        self.assertIsInstance(actual_metadata.modified, datetime)

    def test_swap_new_row(self):
        """Swap New row to Current row."""
        SDNFallbackMetadata.objects.create(
            file_checksum="A",
            import_state="New",
            download_timestamp=self.download_timestamp,
        )

        SDNFallbackMetadata.swap_all_states()

        actual_rows = SDNFallbackMetadata.objects.all()
        self.assertEqual(len(actual_rows), 1)
        self.assertEqual(actual_rows[0].import_state, 'Current')

    def test_swap_current_row(self):
        """Swap Current row to Discard row."""
        SDNFallbackMetadata.objects.create(
            file_checksum="A",
            import_state="Current",
            download_timestamp=self.download_timestamp,
        )
        # this is needed to bypass the requirement to always have a 'Current'
        SDNFallbackMetadata.objects.create(
            file_checksum="A",
            import_state="New",
            download_timestamp=self.download_timestamp,
        )

        SDNFallbackMetadata.swap_all_states()

        actual_row = SDNFallbackMetadata.objects.filter(file_checksum="A")[0]
        self.assertEqual(actual_row.import_state, 'Discard')

    def test_swap_discard_row(self):
        """Discard row gets deleted when swapping rows."""
        SDNFallbackMetadata.objects.create(
            file_checksum="A",
            import_state="Discard",
            download_timestamp=self.download_timestamp,
        )

        SDNFallbackMetadata.swap_all_states()

        actual_rows = SDNFallbackMetadata.objects.all()
        self.assertEqual(len(actual_rows), 0)

    def test_swap_twice_one_row(self):
        """Swapping one row twice without adding a new file should result in an error."""
        SDNFallbackMetadata.objects.create(
            file_checksum="A",
            import_state="New",
            download_timestamp=self.download_timestamp,
        )
        expected_logs = [
            (
                self.LOGGER_NAME,
                'WARNING',
                "Expected a row in the 'Current' import_state after swapping, but there are none."
            ),
        ]

        SDNFallbackMetadata.swap_all_states()
        with self.assertRaises(SDNFallbackMetadata.DoesNotExist):
            with LogCapture(self.LOGGER_NAME) as log:
                SDNFallbackMetadata.swap_all_states()
                log.check_present(*expected_logs)

        self.assertEqual(len(SDNFallbackMetadata.objects.all()), 1)
        existing_a_metadata = SDNFallbackMetadata.objects.filter(file_checksum="A")[0]
        self.assertEqual(existing_a_metadata.import_state, 'Current')

    def test_swap_all_non_existent_rows(self):
        """Swapping all shouldn't break / do anything if there are no existing rows."""

        SDNFallbackMetadata.swap_all_states()
        self.assertEqual(len(SDNFallbackMetadata.objects.all()), 0)

    def test_swap_all_to_use_new_metadata_row(self):
        """
        Test what happens when we want to set the 'New' row to the 'Current' row in a
        normal scenario (e.g. when rows exist in all three import_states).
        """
        SDNFallbackMetadata.objects.create(
            file_checksum="A",
            import_state="New",
            download_timestamp=self.download_timestamp,
        )
        SDNFallbackMetadata.objects.create(
            file_checksum="B",
            import_state="Current",
            download_timestamp=self.download_timestamp,
        )
        SDNFallbackMetadata.objects.create(
            file_checksum="C",
            import_state="Discard",
            download_timestamp=self.download_timestamp,
        )

        SDNFallbackMetadata.swap_all_states()

        self.assertEqual(len(SDNFallbackMetadata.objects.all()), 2)
        existing_a_metadata = SDNFallbackMetadata.objects.filter(file_checksum="A")[0]
        self.assertEqual(existing_a_metadata.import_state, 'Current')
        existing_b_metadata = SDNFallbackMetadata.objects.filter(file_checksum="B")[0]
        self.assertEqual(existing_b_metadata.import_state, 'Discard')
        existing_c_metadata = SDNFallbackMetadata.objects.filter(file_checksum="C")
        self.assertEqual(len(existing_c_metadata), 0)

    def test_swap_all_rollback(self):
        """
        Make sure that the rollback works if there are issues when swapping all of the rows.
        """
        SDNFallbackMetadata.objects.create(
            file_checksum="A",
            import_state="Current",
            download_timestamp=self.download_timestamp,
        )
        SDNFallbackMetadata.objects.create(
            file_checksum="B",
            import_state="Discard",
            download_timestamp=self.download_timestamp,
        )

        expected_logs = [
            (
                self.LOGGER_NAME,
                'WARNING',
                "Expected a row in the 'Current' import_state after swapping, but there are none."
            ),
        ]

        with self.assertRaises(SDNFallbackMetadata.DoesNotExist):
            with LogCapture(self.LOGGER_NAME) as log:
                SDNFallbackMetadata.swap_all_states()
                log.check_present(*expected_logs)

        self.assertEqual(len(SDNFallbackMetadata.objects.all()), 2)
        existing_a_metadata = SDNFallbackMetadata.objects.filter(file_checksum="A")[0]
        self.assertEqual(existing_a_metadata.import_state, 'Current')
        existing_b_metadata = SDNFallbackMetadata.objects.filter(file_checksum="B")[0]
        self.assertEqual(existing_b_metadata.import_state, 'Discard')
