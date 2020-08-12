

import json
from urllib.parse import urlencode
from uuid import uuid4

import httpretty
import requests
from django.conf import settings
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.test.factories import (
    ConditionalOfferFactory,
    EnterpriseCustomerConditionFactory,
    EnterpriseOfferFactory,
    EnterprisePercentageDiscountBenefitFactory
)
from ecommerce.extensions.voucher.models import CouponVouchers

ProductClass = get_model('catalogue', 'ProductClass')


def raise_timeout(request, uri, headers):  # pylint: disable=unused-argument
    raise requests.Timeout('Connection timed out.')


class EnterpriseServiceMockMixin:
    """
    Mocks for the Open edX service 'Enterprise Service' responses.
    """
    ENTERPRISE_CUSTOMER_URL = '{}enterprise-customer/'.format(
        settings.ENTERPRISE_API_URL,
    )
    ENTERPRISE_CUSTOMER_BASIC_LIST_URL = '{}enterprise-customer/basic_list/'.format(
        settings.ENTERPRISE_API_URL,
    )
    ENTERPRISE_LEARNER_URL = '{}enterprise-learner/'.format(
        settings.ENTERPRISE_API_URL,
    )
    ENTERPRISE_COURSE_ENROLLMENT_URL = '{}enterprise-course-enrollment/'.format(
        settings.ENTERPRISE_API_URL,
    )
    ENTERPRISE_CATALOG_URL = '{}enterprise-catalogs/'.format(
        settings.ENTERPRISE_CATALOG_API_URL
    )
    ENTERPRISE_CATALOG_URL_CUSTOMER_RESOURCE = '{}enterprise-customer/'.format(
        settings.ENTERPRISE_CATALOG_API_URL
    )
    LEGACY_ENTERPRISE_CATALOG_URL = '{}enterprise_catalogs/'.format(
        settings.ENTERPRISE_API_URL
    )

    def setUp(self):
        super(EnterpriseServiceMockMixin, self).setUp()
        self.course_run = CourseFactory()

    def mock_enterprise_customer_list_api_get(self):
        """
        Helper function to register the enterprise customer API endpoint.
        """
        enterprise_customer_api_response = [
            {
                'uuid': str(uuid4()),
                'name': "Enterprise Customer 1",
            },
            {
                'uuid': str(uuid4()),
                'name': "Enterprise Customer 2",
            },
        ]

        enterprise_customer_api_response_json = json.dumps(enterprise_customer_api_response)
        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri=self.ENTERPRISE_CUSTOMER_BASIC_LIST_URL,
            body=enterprise_customer_api_response_json,
            content_type='application/json'
        )

    def mock_enterprise_catalog_api_get(self, enterprise_catalog_uuid, custom_response=None):
        """
        Helper function to register the legacy enterprise catalog API endpoint using httpretty.
        """
        enterprise_catalog_api_response = {
            "count": 60,
            "next": "{}{}/?page=2".format(self.LEGACY_ENTERPRISE_CATALOG_URL, enterprise_catalog_uuid),
            "previous": None,
            "results": [
                {
                    "full_description": "kjhl",
                    "short_description": "jhgh",
                    "card_image_url": None,
                    "content_type": "course",
                    "course_runs": [],
                    "title": "Test Course for enrollment codes",
                    "key": "edX+123",
                    "aggregation_key": "course:edX+123"
                },
                {
                    "full_description": None,
                    "short_description": None,
                    "card_image_url": None,
                    "content_type": "course",
                    "course_runs": [
                        {
                            "end": "2019-12-31T00:00:00Z",
                            "start": "2018-09-01T00:00:00Z",
                            "enrollment_end": "2018-12-31T00:00:00Z",
                            "key": "course-v1:Mattx+TCE2E+2018",
                            "enrollment_start": "2018-08-01T00:00:00Z"
                        }
                    ],
                    "title": "TestCourseE2E",
                    "key": "Mattx+TCE2E",
                    "aggregation_key": "course:Mattx+TCE2E"
                },
                {
                    "full_description": None,
                    "short_description": None,
                    "card_image_url": None,
                    "content_type": "course",
                    "course_runs": [
                        {
                            "end": "2019-05-01T00:00:00Z",
                            "start": "2018-05-01T00:00:00Z",
                            "enrollment_end": None,
                            "key": "course-v1:MAX+MAX101+2018_T1",
                            "enrollment_start": None
                        },
                        {
                            "end": "2019-05-01T00:00:00Z",
                            "start": "2030-01-01T00:00:00Z",
                            "enrollment_end": None,
                            "key": "course-v1:MAX+MAX101+2018_R2",
                            "enrollment_start": None
                        }
                    ],
                    "title": "MA Info",
                    "key": "MAX+MAX101",
                    "aggregation_key": "course:MAX+MAX101"
                }
            ]
        }
        enterprise_catalog_api_response = custom_response or enterprise_catalog_api_response
        enterprise_catalog_api_body = json.dumps(enterprise_catalog_api_response)

        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{}{}/'.format(self.LEGACY_ENTERPRISE_CATALOG_URL, enterprise_catalog_uuid),
            body=enterprise_catalog_api_body,
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
                        }
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

    def mock_assignable_enterprise_condition_calls(self, uuid):
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        catalog_contains_content_response = {
            'contains_content_items': True
        }
        self.mock_access_token_response()
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{}{}/contains_content_items/'.format(self.ENTERPRISE_CATALOG_URL, uuid),
            body=json.dumps(catalog_contains_content_response),
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
                            }
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

    def mock_catalog_contains_course_runs(
            self,
            course_run_ids,
            enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=None,
            contains_content=True,
            raise_exception=False
    ):
        self.mock_access_token_response()
        query_params = urlencode({'course_run_ids': course_run_ids}, True)
        body = raise_timeout if raise_exception else json.dumps({'contains_content_items': contains_content})
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{api_url}{enterprise_customer_uuid}/contains_content_items/?{query_params}'.format(
                api_url=self.ENTERPRISE_CATALOG_URL_CUSTOMER_RESOURCE,
                enterprise_customer_uuid=enterprise_customer_uuid,
                query_params=query_params
            ),
            body=body,
            content_type='application/json'
        )
        if enterprise_customer_catalog_uuid:
            httpretty.register_uri(
                method=httpretty.GET,
                uri='{api_url}{customer_catalog_uuid}/contains_content_items/?{query_params}'.format(
                    api_url=self.ENTERPRISE_CATALOG_URL,
                    customer_catalog_uuid=enterprise_customer_catalog_uuid,
                    query_params=query_params
                ),
                body=body,
                content_type='application/json'
            )

    def prepare_enterprise_offer(self, percentage_discount_value=100, enterprise_customer_name=None):
        benefit = EnterprisePercentageDiscountBenefitFactory(value=percentage_discount_value)
        if enterprise_customer_name is not None:
            condition = EnterpriseCustomerConditionFactory(enterprise_customer_name=enterprise_customer_name)
        else:
            condition = EnterpriseCustomerConditionFactory()
        enterprise_offer = EnterpriseOfferFactory(partner=self.partner, benefit=benefit, condition=condition)
        self.mock_enterprise_learner_api(
            learner_id=self.user.id,
            enterprise_customer_uuid=str(condition.enterprise_customer_uuid),
            course_run_id=self.course_run.id,
        )
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            condition.enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=condition.enterprise_customer_catalog_uuid,
        )
        return enterprise_offer

    def mock_with_access_to(self,
                            enterprise_id,
                            enterprise_data_api_group,
                            expected_response,
                            raise_exception=False):
        self.mock_access_token_response()
        query_params = urlencode({
            'permissions': [enterprise_data_api_group],
            'enterprise_id': enterprise_id,
        }, True)
        body = raise_timeout if raise_exception else json.dumps(expected_response)
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{}enterprise-customer/with_access_to/?{}'.format(
                self.site.siteconfiguration.enterprise_api_url,
                query_params
            ),
            body=body,
            content_type='application/json'
        )

    def mock_enterprise_catalog_api(self, enterprise_customer_uuid, raise_exception=None):
        """
        Helper function to register the enterprise catalog API endpoint.
        """
        enterprise_catalog_api_response = {
            'count': 10,
            'num_pages': 3,
            'current_page': 2,
            'results': [
                {
                    'enterprise_customer': '6ae013d4-c5c4-474d-8da9-0e559b2448e2',
                    'uuid': '869d26dd-2c44-487b-9b6a-24eee973f9a4',
                    'title': 'batman_catalog'
                },
                {
                    'enterprise_customer': '6ae013d4-c5c4-474d-8da9-0e559b2448e2',
                    'uuid': '1a61de70-f8e8-4e8c-a76e-01783a930ae6',
                    'title': 'new catalog'
                }
            ],
            'next': "{}?enterprise_customer={}&page=3".format(self.ENTERPRISE_CATALOG_URL, enterprise_customer_uuid),
            'previous': "{}?enterprise_customer={}".format(self.ENTERPRISE_CATALOG_URL, enterprise_customer_uuid),
            'start': 0,
        }

        self.mock_access_token_response()
        body = raise_timeout if raise_exception else json.dumps(enterprise_catalog_api_response)
        httpretty.register_uri(
            method=httpretty.GET,
            uri='{}'.format(self.LEGACY_ENTERPRISE_CATALOG_URL),
            body=body,
            content_type='application/json'
        )


class EnterpriseDiscountTestMixin:
    """
    Test mixin for EnterpriseDiscountMixin.
    """

    def setUp(self):
        super(EnterpriseDiscountTestMixin, self).setUp()
        self.discount_offer = self._create_enterprise_offer()

    @staticmethod
    def create_coupon_product():
        """
        Create the product of coupon type and return it.
        """
        coupon_product_class, _ = ProductClass.objects.get_or_create(name=COUPON_PRODUCT_CLASS_NAME)
        return factories.create_product(
            product_class=coupon_product_class,
            title='Test product'
        )

    @staticmethod
    def _create_enterprise_offer():
        """
        Return the enterprise offer.
        """
        return ConditionalOfferFactory.create(
            benefit_id=EnterprisePercentageDiscountBenefitFactory.create().id,
            condition_id=EnterpriseCustomerConditionFactory.create().id,
        )

    def _create_coupon_and_voucher(self, enterprise_contract_metadata=None):
        """
        Create and link the coupon product and voucher, and return the coupon_code and voucher.
        """
        coupon = self.create_coupon_product()
        voucher = factories.VoucherFactory()
        voucher.offers.add(self.discount_offer)
        coupon_vouchers = CouponVouchers.objects.create(coupon=coupon)
        coupon_vouchers.vouchers.add(voucher)

        coupon.attr.enterprise_contract_metadata = enterprise_contract_metadata
        coupon.attr.coupon_vouchers = coupon_vouchers
        coupon.save()
        return coupon.attr.coupon_vouchers.vouchers.first().code, voucher

    def create_order_offer_discount(self, order, enterprise_contract_metadata=None):
        """
        Create the offer discount for order.
        """
        self.discount_offer.enterprise_contract_metadata = enterprise_contract_metadata
        self.discount_offer.save()
        discount = order.discounts.create()
        discount.offer_id = self.discount_offer.id
        discount.save()

    def create_order_voucher_discount(self, order, enterprise_contract_metadata=None):
        """
        Create the voucher discount for order.
        """
        code, voucher = self._create_coupon_and_voucher(
            enterprise_contract_metadata=enterprise_contract_metadata
        )
        discount = order.discounts.create()
        discount.voucher_id = voucher.id
        discount.voucher_code = code
        discount.save()
