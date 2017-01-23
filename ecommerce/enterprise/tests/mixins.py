import json

import httpretty
from django.conf import settings
from django.core.cache import cache


class EnterpriseServiceMockMixin(object):
    """
    Mocks for the Open edX service 'Enterprise Service' responses.
    """
    ENTERPRISE_LEARNER_URL = '{}enterprise-learner/'.format(
        settings.ENTERPRISE_API_URL,
    )

    def setUp(self):
        super(EnterpriseServiceMockMixin, self).setUp()
        cache.clear()

    def mock_enterprise_learner_api(self, catalog_id=1, entitlement_id=1):
        """
        Helper function to register enterprise learner API endpoint.
        """
        enterprise_learner_api_response = {
            'count': 1,
            'num_pages': 1,
            'current_page': 1,
            'results': [
                {
                    'enterprise_customer': {
                        'uuid': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
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
                            'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                            'logo': 'https://open.edx.org/sites/all/themes/edx_open/logo.png'
                        },
                        'enterprise_customer_entitlements': [
                            {
                                'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
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
        learner with invalid API reponse structure.
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

    def mock_enterprise_learner_api_for_failure(self):
        """
        Helper function to register enterprise learner API endpoint for a
        failure.
        """
        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_LEARNER_URL,
            responses=[
                httpretty.Response(body='{}', content_type='application/json', status_code=500)
            ]
        )
