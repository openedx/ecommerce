from __future__ import unicode_literals

import uuid

import ddt
import httpretty
from django.conf import settings
from django.http.response import HttpResponse
from oscar.test.factories import VoucherFactory

from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.enterprise.utils import (
    enterprise_customer_user_needs_consent,
    get_enterprise_customer,
    get_enterprise_customer_uuid,
    get_enterprise_customers,
    get_or_create_enterprise_customer_user,
    set_enterprise_customer_cookie
)
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.testcases import TestCase

TEST_ENTERPRISE_CUSTOMER_UUID = 'cf246b88-d5f6-4908-a522-fc307e0b0c59'


@ddt.ddt
@httpretty.activate
class EnterpriseUtilsTests(EnterpriseServiceMockMixin, TestCase):
    def setUp(self):
        super(EnterpriseUtilsTests, self).setUp()
        self.learner = self.create_user(is_staff=True)
        self.client.login(username=self.learner.username, password=self.password)

    def test_get_enterprise_customers(self):
        """
        Verify that "get_enterprise_customers" returns an appropriate response from the
        "enterprise-customer" Enterprise service API endpoint.
        """
        self.mock_access_token_response()
        self.mock_enterprise_customer_list_api_get()
        response = get_enterprise_customers(self.site)
        self.assertEqual(response[0]['name'], "Enterprise Customer 1")
        self.assertEqual(response[1]['name'], "Enterprise Customer 2")

    def test_get_enterprise_customer(self):
        """
        Verify that "get_enterprise_customer" returns an appropriate response from the
        "enterprise-customer" Enterprise service API endpoint.
        """
        self.mock_access_token_response()
        self.mock_specific_enterprise_customer_api(TEST_ENTERPRISE_CUSTOMER_UUID)
        response = get_enterprise_customer(self.site, TEST_ENTERPRISE_CUSTOMER_UUID)

        self.assertEqual(TEST_ENTERPRISE_CUSTOMER_UUID, response.get('id'))

    @ddt.data(
        (
            ['mock_enterprise_learner_api'],
            {'user_id': 5},
        ),
        (
            [
                'mock_enterprise_learner_api_for_learner_with_no_enterprise',
                'mock_enterprise_learner_post_api',
            ],
            {
                'enterprise_customer': TEST_ENTERPRISE_CUSTOMER_UUID,
                'username': 'the_j_meister',
            },
        )
    )
    @ddt.unpack
    def test_post_enterprise_customer_user(self, mock_helpers, expected_return):
        """
        Verify that "get_enterprise_customer" returns an appropriate response from the
        "enterprise-customer" Enterprise service API endpoint.
        """
        for mock in mock_helpers:
            getattr(self, mock)()

        self.mock_access_token_response()
        response = get_or_create_enterprise_customer_user(
            self.site,
            TEST_ENTERPRISE_CUSTOMER_UUID,
            self.learner.username
        )

        self.assertDictContainsSubset(expected_return, response)

    @httpretty.activate
    def test_ecu_needs_consent(self):
        opts = {
            'ec_uuid': 'fake-uuid',
            'course_id': 'course-v1:real+course+id',
            'username': 'johnsmith',
        }
        kw = {
            'enterprise_customer_uuid': 'fake-uuid',
            'course_id': 'course-v1:real+course+id',
            'username': 'johnsmith',
            'site': self.site
        }
        self.mock_access_token_response()
        self.mock_consent_get(**opts)
        self.assertEqual(enterprise_customer_user_needs_consent(**kw), False)
        self.mock_consent_missing(**opts)
        self.assertEqual(enterprise_customer_user_needs_consent(**kw), True)
        self.mock_consent_not_required(**opts)
        self.assertEqual(enterprise_customer_user_needs_consent(**kw), False)

    def test_get_enterprise_customer_uuid(self):
        """
        Verify that enterprise customer UUID is returned for a voucher with an associated enterprise customer.
        """
        enterprise_customer_uuid = uuid.uuid4()
        voucher, __ = prepare_voucher(enterprise_customer=enterprise_customer_uuid)

        self.assertEqual(
            enterprise_customer_uuid,
            get_enterprise_customer_uuid(voucher.code),
        )

    def test_get_enterprise_customer_uuid_non_existing_voucher(self):
        """
        Verify that None is returned when voucher with given code does not exist.
        """
        voucher = VoucherFactory()
        self.assertIsNone(get_enterprise_customer_uuid(voucher.code))

    def test_get_enterprise_customer_uuid_non_existing_conditional_offer(self):
        """
        Verify that None is returned if voucher exists but conditional offer
        does not exist.
        """
        voucher = VoucherFactory()
        self.assertIsNone(get_enterprise_customer_uuid(voucher.code))

    def test_set_enterprise_customer_cookie(self):
        """
        Verify that enterprise cookies are set properly.
        """
        enterprise_customer_uuid = uuid.uuid4()
        response = HttpResponse()

        result = set_enterprise_customer_cookie(self.site, response, enterprise_customer_uuid)

        cookie = result.cookies[settings.ENTERPRISE_CUSTOMER_COOKIE_NAME]
        self.assertEqual(str(enterprise_customer_uuid), cookie.value)

    def test_set_enterprise_customer_cookie_empty_cookie_domain(self):
        """
        Verify that enterprise cookie is not set if base_cookie_domain is empty
        in site configuration.
        """
        self.site.siteconfiguration.base_cookie_domain = ''
        self.site.siteconfiguration.save()

        enterprise_customer_uuid = uuid.uuid4()
        response = HttpResponse()

        result = set_enterprise_customer_cookie(self.site, response, enterprise_customer_uuid)

        self.assertNotIn(settings.ENTERPRISE_CUSTOMER_COOKIE_NAME, result.cookies)
