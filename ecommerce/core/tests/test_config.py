""" Tests for CoreAppConfig """
import mock
from django.db import OperationalError
from django.test import SimpleTestCase

from ecommerce import core

from ecommerce.core.config import CoreAppConfig


class TestAppConfig(SimpleTestCase):
    """ Test suite for CoreAppConfig class """
    def test_ready_validates_configuration(self):
        """ Tests that method `ready` invokes `models.validate_configuration` method"""
        config = CoreAppConfig('core', core)

        with mock.patch('ecommerce.core.models.validate_configuration') as patched_validate:
            config.ready()

            self.assertTrue(patched_validate.called)

    def test_ready_validate_suppresses_operational_error(self):
        """ Tests that django.db.OperationalError is suppressed and logged in `ready` method """
        config = CoreAppConfig('core', core)

        with mock.patch('ecommerce.core.models.validate_configuration') as patched_validate:
            with mock.patch('ecommerce.core.config.log') as patched_log:
                patched_validate.side_effect = OperationalError
                config.ready()

                self.assertTrue(patched_validate.called)
                patched_log.exception.assert_called_once_with(config.OPERATIONAL_ERROR_MESSAGE)
