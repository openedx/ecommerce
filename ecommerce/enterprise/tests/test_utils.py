from __future__ import unicode_literals

import uuid

import ddt
import httpretty
from django.conf import settings
from django.http.response import HttpResponse
from oscar.test.factories import VoucherFactory

from ecommerce.core.tests.decorators import mock_enterprise_api_client
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

    @mock_enterprise_api_client
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

        response = get_or_create_enterprise_customer_user(
            self.site,
            TEST_ENTERPRISE_CUSTOMER_UUID,
            self.learner.username
        )

        self.assertDictContainsSubset(expected_return, response)

    @ddt.data(
        (True, True),
        (False, False),
    )
    @ddt.unpack
    def test_ecu_needs_consent_no_link(self, ec_consent_enabled, expected_consent_requirement):
        """
        Test that when there's no EnterpriseCustomerUser, the consent requirement comes down
        to whether the EnterpriseCustomer wants consent.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        enterprise_customer_uuid = TEST_ENTERPRISE_CUSTOMER_UUID
        self.mock_specific_enterprise_customer_api(enterprise_customer_uuid, consent_enabled=ec_consent_enabled)

        consent_needed = enterprise_customer_user_needs_consent(
            self.site,
            TEST_ENTERPRISE_CUSTOMER_UUID,
            'course-v1:edX+DemoX+Demo_Course',
            'admin'
        )
        self.assertEqual(consent_needed, expected_consent_requirement)

    @ddt.data(
        (True, False, True, True, False),
        (False, True, True, True, False),
        (False, False, True, True, True),
        (False, False, True, False, True),
        (False, False, False, True, False),
        (False, False, False, False, False),
    )
    @ddt.unpack
    def test_ecu_needs_consent_link_exists(
            self,
            account_consent_provided,
            course_consent_provided,
            consent_enabled,
            results_present,
            expected_consent_requirement
    ):
        self.mock_access_token_response()
        enterprise_customer_uuid = TEST_ENTERPRISE_CUSTOMER_UUID
        self.mock_enterprise_learner_api(
            enterprise_customer_uuid=enterprise_customer_uuid,
            consent_provided=account_consent_provided,
            consent_enabled=consent_enabled,
        )
        self.mock_enterprise_course_enrollment_api(
            consent_granted=course_consent_provided,
            results_present=results_present,
        )

        consent_needed = enterprise_customer_user_needs_consent(
            self.site,
            TEST_ENTERPRISE_CUSTOMER_UUID,
            'course-v1:edX+DemoX+Demo_Course',
            'admin'
        )
        self.assertEqual(consent_needed, expected_consent_requirement)

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
