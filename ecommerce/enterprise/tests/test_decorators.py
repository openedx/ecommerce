

import uuid

import ddt
import httpretty
from django.conf import settings
from django.http.response import HttpResponse
from django.test import RequestFactory
from oscar.test.factories import VoucherFactory

from ecommerce.enterprise import decorators
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.testcases import TestCase


@ddt.ddt
@httpretty.activate
class EnterpriseDecoratorsTests(EnterpriseServiceMockMixin, TestCase):

    @staticmethod
    def _mock_view(*args, **kwargs):  # pylint: disable=unused-argument
        """
        Mock django view to use for testing decorator.
        """
        return HttpResponse()

    def test_set_enterprise_cookie(self):
        """
        Validate that a cookie is set with UUID of the enterprise customer
        associated with the voucher of given code.
        """
        enterprise_customer_uuid = uuid.uuid4()
        voucher, __ = prepare_voucher(enterprise_customer=enterprise_customer_uuid)
        request = RequestFactory().get('/', data={'code': voucher.code})
        request.site = self.site
        response = decorators.set_enterprise_cookie(self._mock_view)(request)

        cookie = response.cookies[settings.ENTERPRISE_CUSTOMER_COOKIE_NAME]
        self.assertEqual(str(enterprise_customer_uuid), cookie.value)
        self.assertEqual(60, cookie.get('max-age'))

    def test_set_enterprise_cookie_no_code(self):
        """
        Validate that no cookie is set if voucher code is not provided in url parameters.
        """
        request = RequestFactory().get('/')
        request.site = self.site
        response = decorators.set_enterprise_cookie(self._mock_view)(request)

        self.assertNotIn(settings.ENTERPRISE_CUSTOMER_COOKIE_NAME, response.cookies)

    def test_set_enterprise_cookie_no_enterprise_customer(self):
        """
        Validate that no cookie is set if no enterprise customer is
        associated with the voucher of given code.
        """
        voucher = VoucherFactory()
        request = RequestFactory().get('/', data={'code': voucher.code})
        request.site = self.site
        response = decorators.set_enterprise_cookie(self._mock_view)(request)

        self.assertNotIn(settings.ENTERPRISE_CUSTOMER_COOKIE_NAME, response.cookies)
