import json

import httpretty
from django.conf import settings
from django.core.cache import cache


class EnterpriseServiceMockMixin(object):
    """
    Mocks for the Open edX service 'Enterprise Service' responses.
    """
    ENTERPRISE_CUSTOMER_URL = '{}enterprise-customer/'.format(
        settings.ENTERPRISE_API_URL,
    )
    ENTERPRISE_LEARNER_URL = '{}enterprise-learner/'.format(
        settings.ENTERPRISE_API_URL,
    )

    def setUp(self):
        super(EnterpriseServiceMockMixin, self).setUp()
        cache.clear()

    def mock_specific_enterprise_customer_api(self, uuid):
        """
        Helper function to register the enterprise customer API endpoint.
        """
        enterprise_customer_api_response = {
            'uuid': uuid,
            'name': 'TestShib',
            'catalog': 0,
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
                    'entitlement_id': 0
                }
            ]
        }
        enterprise_customer_api_response_json = json.dumps(enterprise_customer_api_response)

        httpretty.register_uri(
            method=httpretty.GET,
            uri='{}{}/'.format(self.ENTERPRISE_CUSTOMER_URL, uuid),
            body=enterprise_customer_api_response_json,
            content_type='application/json'
        )

    def mock_enterprise_customer_api_not_found(self, uuid):
        """
        Helper function to register the enterprise customer API endpoint.
        """
        enterprise_customer_api_response = {
            'detail': 'Not found.'
        }
        enterprise_customer_api_response_json = json.dumps(enterprise_customer_api_response)

        httpretty.register_uri(
            method=httpretty.GET,
            uri='{}{}/'.format(self.ENTERPRISE_CUSTOMER_URL, uuid),
            body=enterprise_customer_api_response_json,
            content_type='application/json',
            status=404,
        )

    def mock_enterprise_learner_api(
            self,
            catalog_id=1,
            entitlement_id=1,
            learner_id=1,
            enterprise_customer_uuid='cf246b88-d5f6-4908-a522-fc307e0b0c59'
    ):
        """
        Helper function to register enterprise learner API endpoint.
        """
        enterprise_learner_api_response = {
            'count': 1,
            'num_pages': 1,
            'current_page': 1,
            'results': [
                {
                    'id': learner_id,
                    'enterprise_customer': {
                        'uuid': enterprise_customer_uuid,
                        'name': 'TestShib',
                        'catalog': catalog_id,
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
                            'enterprise_customer': enterprise_customer_uuid,
                            'logo': 'https://open.edx.org/sites/all/themes/edx_open/logo.png'
                        },
                        'enterprise_customer_entitlements': [
                            {
                                'enterprise_customer': enterprise_customer_uuid,
                                'entitlement_id': entitlement_id
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
            ],
            'next': None,
            'start': 0,
            'previous': None
        }
        enterprise_learner_api_response_json = json.dumps(enterprise_learner_api_response)

        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_LEARNER_URL,
            body=enterprise_learner_api_response_json,
            content_type='application/json'
        )

    def mock_enterprise_learner_post_api(self):
        """
        Helper function to register the enterprise learner POST API endpoint.
        """
        enterprise_learner_api_response = {
            'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
            'username': 'the_j_meister',
        }
        enterprise_learner_api_response_json = json.dumps(enterprise_learner_api_response)

        httpretty.register_uri(
            method=httpretty.POST,
            uri=self.ENTERPRISE_LEARNER_URL,
            body=enterprise_learner_api_response_json,
            content_type='application/json'
        )

    def mock_enterprise_learner_api_for_learner_with_no_enterprise(self):
        """
        Helper function to register enterprise learner API endpoint for a
        learner which is not associated with any enterprise.
        """
        enterprise_learner_api_response = {
            'count': 0,
            'num_pages': 1,
            'current_page': 1,
            'results': [],
            'next': None,
            'start': 0,
            'previous': None
        }
        enterprise_learner_api_response_json = json.dumps(enterprise_learner_api_response)

        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_LEARNER_URL,
            body=enterprise_learner_api_response_json,
            content_type='application/json'
        )

    def mock_enterprise_learner_api_for_learner_with_invalid_response(self):
        """
        Helper function to register enterprise learner API endpoint for a
        learner with invalid API response structure.
        """
        enterprise_learner_api_response = {
            'count': 0,
            'num_pages': 1,
            'current_page': 1,
            'results': [
                {
                    'invalid-unexpected-key': {
                        'enterprise_customer': {
                            'uuid': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                            'name': 'TestShib',
                            'catalog': 1,
                            'active': True,
                            'site': {
                                'domain': 'example.com',
                                'name': 'example.com'
                            },
                            'enterprise_customer_entitlements': [
                                {
                                    'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                                    'entitlement_id': 1
                                }
                            ]
                        },
                    }
                }
            ],
            'next': None,
            'start': 0,
            'previous': None
        }
        enterprise_learner_api_response_json = json.dumps(enterprise_learner_api_response)

        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_LEARNER_URL,
            body=enterprise_learner_api_response_json,
            content_type='application/json'
        )

    def mock_enterprise_learner_api_for_learner_with_invalid_entitlements_response(self):
        """
        Helper function to register enterprise learner API endpoint for a
        learner with partial invalid API response structure for the enterprise
        customer entitlements.
        """
        enterprise_learner_api_response = {
            'count': 0,
            'num_pages': 1,
            'current_page': 1,
            'results': [
                {
                    'enterprise_customer': {
                        'uuid': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                        'name': 'TestShib',
                        'catalog': 1,
                        'active': True,
                        'site': {
                            'domain': 'example.com',
                            'name': 'example.com'
                        },
                        'invalid-unexpected-enterprise_customer_entitlements-key': [
                            {
                                'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                                'entitlement_id': 1
                            }
                        ]
                    }
                }
            ],
            'next': None,
            'start': 0,
            'previous': None
        }
        enterprise_learner_api_response_json = json.dumps(enterprise_learner_api_response)

        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_LEARNER_URL,
            body=enterprise_learner_api_response_json,
            content_type='application/json'
        )

    def mock_enterprise_learner_api_for_failure(self):
        """
        Helper function to register enterprise learner API endpoint for a
        failure.
        """
        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_LEARNER_URL,
            status=500,
        )

    def mock_learner_entitlements_api_failure(self, learner_id, status=500):
        """
        Helper function to return 500 error while accessing learner entitlements api endpoint.
        """
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{base_url}{learner_id}/entitlements/'.format(
                base_url=self.ENTERPRISE_LEARNER_URL, learner_id=learner_id,
            ),
            responses=[
                httpretty.Response(body='{}', content_type='application/json', status=status)
            ]
        )

    def mock_enterprise_learner_entitlements_api(self, learner_id=1, entitlement_id=1, require_consent=False):
        """
        Helper function to register enterprise learner entitlements API endpoint.
        """
        enterprise_learner_entitlements_api_response = {
            'entitlements': [
                {
                    'entitlement_id': entitlement_id,
                    'requires_consent': require_consent,
                }
            ]
        }
        learner_entitlements_json = json.dumps(enterprise_learner_entitlements_api_response)

        httpretty.register_uri(
            method=httpretty.GET,
            uri='{base_url}{learner_id}/entitlements/'.format(
                base_url=self.ENTERPRISE_LEARNER_URL, learner_id=learner_id,
            ),
            body=learner_entitlements_json,
            content_type='application/json'
        )
