import copy
import json
from urllib import urlencode
from uuid import uuid4

import httpretty
import requests
from django.conf import settings


def raise_timeout(request, uri, headers):  # pylint: disable=unused-argument
    raise requests.Timeout('Connection timed out.')


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
    ENTERPRISE_COURSE_ENROLLMENT_URL = '{}enterprise-course-enrollment/'.format(
        settings.ENTERPRISE_API_URL,
    )

    def mock_enterprise_customer_list_api_get(self):
        """
        Helper function to register the enterprise customer API endpoint.
        """
        enterprise_customer_data = {
            'uuid': str(uuid4()),
            'name': "Enterprise Customer 1",
            'catalog': 0,
            'active': True,
            'site': {
                'domain': 'example.com',
                'name': 'example.com'
            },
            'enable_data_sharing_consent': True,
            'enforce_data_sharing_consent': 'at_login',
            'branding_configuration': {
                'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                'logo': 'https://open.edx.org/sites/all/themes/edx_open/logo.png'
            },
            'enterprise_customer_entitlements': [
                {
                    'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                    'entitlement_id': 0
                }
            ],
            'contact_email': "administrator@enterprisecustomer.com",
        }

        enterprise_customer2_data = copy.deepcopy(enterprise_customer_data)
        enterprise_customer2_data['uuid'] = str(uuid4())
        enterprise_customer2_data['name'] = 'Enterprise Customer 2'

        enterprise_customer_api_response = {
            'results':
                [
                    enterprise_customer_data,
                    enterprise_customer2_data
                ]
        }

        enterprise_customer_api_response_json = json.dumps(enterprise_customer_api_response)
        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_CUSTOMER_URL,
            body=enterprise_customer_api_response_json,
            content_type='application/json'
        )

    def mock_specific_enterprise_customer_api(self, uuid, name='BigEnterprise', contact_email='', consent_enabled=True):
        """
        Helper function to register the enterprise customer API endpoint.
        """
        enterprise_customer_api_response = {
            'uuid': str(uuid),
            'name': name,
            'catalog': 0,
            'active': True,
            'site': {
                'domain': 'example.com',
                'name': 'example.com'
            },
            'enable_data_sharing_consent': consent_enabled,
            'enforce_data_sharing_consent': 'at_login',
            'branding_configuration': {
                'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                'logo': 'https://open.edx.org/sites/all/themes/edx_open/logo.png'
            },
            'enterprise_customer_entitlements': [
                {
                    'enterprise_customer': 'cf246b88-d5f6-4908-a522-fc307e0b0c59',
                    'entitlement_id': 0
                }
            ],
            'contact_email': contact_email,
        }
        enterprise_customer_api_response_json = json.dumps(enterprise_customer_api_response)

        self.mock_access_token_response()
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

        self.mock_access_token_response()
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
            enterprise_customer_uuid='cf246b88-d5f6-4908-a522-fc307e0b0c59',
            consent_enabled=True,
            consent_provided=True,
            course_run_id='course-v1:edX DemoX Demo_Course'
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
                        'name': 'BigEnterprise',
                        'catalog': catalog_id,
                        'active': True,
                        'site': {
                            'domain': 'example.com',
                            'name': 'example.com'
                        },
                        'enable_data_sharing_consent': consent_enabled,
                        'enforce_data_sharing_consent': 'at_login',
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
                    'data_sharing_consent_records': [
                        {
                            "username": "verified",
                            "enterprise_customer_uuid": enterprise_customer_uuid,
                            "exists": True,
                            "consent_provided": consent_provided,
                            "consent_required": consent_enabled and not consent_provided,
                            "course_id": course_run_id,
                        }
                    ]
                }
            ],
            'next': None,
            'start': 0,
            'previous': None
        }
        enterprise_learner_api_response_json = json.dumps(enterprise_learner_api_response)

        self.mock_access_token_response()
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

        self.mock_access_token_response()
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

        self.mock_access_token_response()
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
                            'name': 'BigEnterprise',
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

        self.mock_access_token_response()
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
                        'name': 'BigEnterprise',
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

        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_LEARNER_URL,
            body=enterprise_learner_api_response_json,
            content_type='application/json'
        )

    def mock_enterprise_learner_api_raise_exception(self):
        """
        Helper function to register enterprise learner API endpoint and raise an exception.
        """
        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_LEARNER_URL,
            body=raise_timeout
        )

    def mock_enterprise_learner_api_for_failure(self):
        """
        Helper function to register enterprise learner API endpoint for a
        failure.
        """
        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_LEARNER_URL,
            status=500,
        )

    def mock_learner_entitlements_api_failure(self, learner_id, status=500):
        """
        Helper function to return 500 error while accessing learner entitlements api endpoint.
        """
        self.mock_access_token_response()
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

        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{base_url}{learner_id}/entitlements/'.format(
                base_url=self.ENTERPRISE_LEARNER_URL, learner_id=learner_id,
            ),
            body=learner_entitlements_json,
            content_type='application/json'
        )

    def mock_enterprise_course_enrollment_api(
            self,
            ec_user_id=1,
            consent_granted=True,
            course_id='course-v1:edX+DemoX+Demo_Course',
            results_present=True
    ):
        """
        Helper function to register enterprise course enrollment API endpoint for a
        learner with an existing enterprise enrollment in a course.
        """
        enterprise_enrollment_api_response = {
            'count': 1,
            'num_pages': 1,
            'current_page': 1,
            'results': [
                {
                    'enterprise_customer_user': ec_user_id,
                    'consent_granted': consent_granted,
                    'course_id': course_id,
                }
            ],
            'next': None,
            'start': 0,
            'previous': None
        } if results_present else {
            'count': 0,
            'num_pages': 1,
            'current_page': 1,
            'results': [],
            'next': None,
            'start': 0,
            'previous': None
        }
        enterprise_enrollment_api_response_json = json.dumps(enterprise_enrollment_api_response)

        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_COURSE_ENROLLMENT_URL,
            body=enterprise_enrollment_api_response_json,
            content_type='application/json'
        )

    def mock_consent_response(
            self,
            username,
            course_id,
            ec_uuid,
            method=httpretty.GET,
            granted=True,
            required=False,
            exists=True,
            response_code=None
    ):
        response_body = {
            'username': username,
            'course_id': course_id,
            'enterprise_customer_uuid': ec_uuid,
            'consent_provided': granted,
            'consent_required': required,
            'exists': exists,
        }

        self.mock_access_token_response()
        httpretty.register_uri(
            method=method,
            uri=self.site.siteconfiguration.build_lms_url('/consent/api/v1/data_sharing_consent'),
            content_type='application/json',
            body=json.dumps(response_body),
            status=response_code or 200,
        )

    def mock_consent_get(self, username, course_id, ec_uuid):
        self.mock_consent_response(
            username,
            course_id,
            ec_uuid
        )

    def mock_consent_missing(self, username, course_id, ec_uuid):
        self.mock_consent_response(
            username,
            course_id,
            ec_uuid,
            exists=False,
            granted=False,
            required=True,
        )

    def mock_consent_not_required(self, username, course_id, ec_uuid):
        self.mock_consent_response(
            username,
            course_id,
            ec_uuid,
            exists=False,
            granted=False,
            required=False,
        )

    def mock_catalog_contains_course_runs(self, course_run_ids, enterprise_customer_uuid,
                                          enterprise_customer_catalog_uuid=None, contains_content=True,
                                          raise_exception=False):
        self.mock_access_token_response()
        query_params = urlencode({'course_run_ids': course_run_ids}, True)
        body = raise_timeout if raise_exception else json.dumps({'contains_content_items': contains_content})
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{}enterprise-customer/{}/contains_content_items/?{}'.format(
                self.site.siteconfiguration.enterprise_api_url,
                enterprise_customer_uuid,
                query_params
            ),
            body=body,
            content_type='application/json'
        )
        if enterprise_customer_catalog_uuid:
            httpretty.register_uri(
                method=httpretty.GET,
                uri='{}enterprise_catalogs/{}/contains_content_items/?{}'.format(
                    self.site.siteconfiguration.enterprise_api_url,
                    enterprise_customer_catalog_uuid,
                    query_params
                ),
                body=body,
                content_type='application/json'
            )
