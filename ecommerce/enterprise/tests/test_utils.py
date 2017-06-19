from __future__ import unicode_literals

import ddt
import httpretty
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from oscar.test import factories

from ecommerce.core.tests import toggle_switch
from ecommerce.core.tests.decorators import mock_enterprise_api_client
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.enterprise.utils import (enterprise_customer_user_needs_consent, get_enterprise_customer,
                                        get_enterprise_customers, get_enterprise_learner,
                                        get_or_create_enterprise_customer_user, is_user_linked_to_enterprise_customer)

TEST_ENTERPRISE_CUSTOMER_UUID = 'cf246b88-d5f6-4908-a522-fc307e0b0c59'


@ddt.ddt
@httpretty.activate
class EnterpriseUtilsTests(EnterpriseServiceMockMixin):
    def setUp(self):
        super(EnterpriseUtilsTests, self).setUp()
        self.learner = self.create_user(is_staff=True)
        self.client.login(username=self.learner.username, password=self.password)

    def _enable_enterprise(self, is_active=True):
        """
        Enable Enterprise functionality via waffle switch.
        """
        toggle_switch(name=settings.ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH, active=is_active)

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
        uuid = TEST_ENTERPRISE_CUSTOMER_UUID
        self.mock_specific_enterprise_customer_api(uuid, consent_enabled=ec_consent_enabled)

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
        uuid = TEST_ENTERPRISE_CUSTOMER_UUID
        self.mock_enterprise_learner_api(
            enterprise_customer_uuid=uuid,
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

    @mock_enterprise_api_client
    def test_get_enterprise_learner(self):
        """
        Verify that "get_enterprise_learner" returns an appropriate response from the
        "enterprise-learner" Enterprise service API endpoint.
        """
        expected_learner_data = {
            'id': self.learner.id,
            'enterprise_customer': {
                'uuid': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                'name': 'TestShib',
                'catalog': 1,
                'active': True,
                'site': {
                    'domain': 'example.com',
                    'name': 'example.com'
                },
                'enable_data_sharing_consent': True,
                'enforce_data_sharing_consent': 'at_login',
                'enterprise_customer_users': [
                    1
                ],
                'branding_configuration': {
                    'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                    'logo': 'https://open.edx.org/sites/all/themes/edx_open/logo.png'
                },
                'enterprise_customer_entitlements': [
                    {
                        'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                        'entitlement_id': 1
                    }
                ]
            },
            'user_id': 5,
            'user': {
                'username': 'verified',
                'first_name': '',
                'last_name': '',
                'email': 'verified@example.com',
                'is_staff': True,
                'is_active': True,
                'date_joined': '2016-09-01T19:18:26.026495Z'
            },
            'data_sharing_consent': [
                {
                    'user': 1,
                    'state': 'enabled',
                    'enabled': True
                }
            ]
        }
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(learner_id=self.learner.id)

        enterprise_learner = get_enterprise_learner(self.site, self.learner)

        # assert non-None result is returned when enterprise learner with given username exist
        self.assertEqual(enterprise_learner, expected_learner_data)

        enterprise_learner = get_enterprise_learner(self.site, AnonymousUser())
        # assert None is returned when get_enterprise_learner is called with anonymous user
        self.assertIsNone(enterprise_learner)

    @mock_enterprise_api_client
    def test_get_enterprise_learner_when_no_enterprise_learner_exists(self):
        """
        Verify that "get_enterprise_learner" returns an appropriate response from the
        "enterprise-learner" Enterprise service API endpoint.

        Test that get_enterprise_learner returns `None` when there is no user
        associated with the enterpise customer.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api_for_no_learner()

        enterprise_learner = get_enterprise_learner(self.site, self.learner)

        self.assertIsNone(enterprise_learner)

    @mock_enterprise_api_client
    @ddt.data(
        (
            [
                (
                    'mock_enterprise_learner_api',
                    {'enterprise_customer_uuid': TEST_ENTERPRISE_CUSTOMER_UUID, 'learner_id': 7},
                ),
            ],
            lambda: factories.UserFactory(id=7),
            True,
            True,
        ),
        (
            [
                (
                    'mock_enterprise_learner_api',
                    {'enterprise_customer_uuid': TEST_ENTERPRISE_CUSTOMER_UUID, 'learner_id': 7},
                ),
            ],
            AnonymousUser,
            True,
            False,
        ),
        (
            [
                (
                    'mock_enterprise_learner_api',
                    {'enterprise_customer_uuid': TEST_ENTERPRISE_CUSTOMER_UUID, 'learner_id': 7},
                ),
            ],
            lambda: factories.UserFactory(id=7),
            False,
            False,
        ),
        (
            [
                (
                    'mock_enterprise_learner_api_for_no_learner',
                    {},
                ),
            ],
            lambda: factories.UserFactory(id=7),
            True,
            False,
        ),
    )
    @ddt.unpack
    def test_is_user_linked_to_enterprise_customer(
            self, mock_helpers, create_learner, is_enterprise_active, expected_result,
    ):
        """
        Verify that "is_user_linked_to_enterprise_customer" returns an appropriate result.
        """
        self._enable_enterprise(is_enterprise_active)
        self.mock_access_token_response()
        learner = create_learner()

        for mock in mock_helpers:
            mock_func, mock_func_args = mock
            getattr(self, mock_func)(
                **mock_func_args
            )

        result = is_user_linked_to_enterprise_customer(
            self.site, TEST_ENTERPRISE_CUSTOMER_UUID, learner
        )

        # assert True is returned when enterprise learner belongs the enterprise customer
        self.assertEqual(result, expected_result)
