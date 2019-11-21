# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.core.exceptions import ValidationError
import six

from ecommerce.extensions.payment.models import (
    EnterpriseContractMetadata,
    SDNCheckFailure,
)
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
