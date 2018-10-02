# encoding: utf-8
"""Contains the tests for migrate enterprise conditional offers command."""

from __future__ import unicode_literals

import logging
import os
import tempfile
from decimal import Decimal

from django.core.management import CommandError, call_command
from testfixtures import LogCapture

from ecommerce.tests.testcases import TransactionTestCase

logger = logging.getLogger(__name__)
LOGGER_NAME = 'ecommerce.enterprise.management.commands.migrate_enterprise_conditional_offers'


class MigrateEnterpriseConditionalOffersTests(TransactionTestCase):
    """
    Tests the enrollment code creation command.
    """
    tmp_file_path = os.path.join(tempfile.gettempdir(), 'tmp-courses.txt')

    def setUp(self):
        """
        Create test data.
        """
        super(MigrateEnterpriseConditionalOffersTests, self).setUp()

    def test_migrate_voucher(self):
        # test cases include: percentage discount, absolute discount, with enterprise catalog,
        pass

    def test_get_voucher_batch(self):
        # test cases include filtering out non enterprise vouchers and getting the correct inidices
        pass

    def test_handle(self):
        # test cases include handling an error, starting from a non default batch offset
        pass