

import uuid

import ddt
import responses
from django.conf import settings
from django.http.response import HttpResponse
from django.test import RequestFactory
from edx_django_utils.cache import TieredCache
from mock import patch
from oscar.core.loading import get_class
from oscar.test.factories import BasketFactory, VoucherFactory

from ecommerce.core.constants import SYSTEM_ENTERPRISE_ADMIN_ROLE, SYSTEM_ENTERPRISE_LEARNER_ROLE
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.api import get_enterprise_id_for_user
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.enterprise.utils import (
    CUSTOMER_CATALOGS_DEFAULT_RESPONSE,
    create_enterprise_customer_user_consent,
    enterprise_customer_user_needs_consent,
    find_active_enterprise_customer_user,
    get_enterprise_catalog,
    get_enterprise_customer,
    get_enterprise_customer_catalogs,
    get_enterprise_customer_from_enterprise_offer,
    get_enterprise_customer_reply_to_email,
    get_enterprise_customer_sender_alias,
    get_enterprise_customer_uuid,
    get_enterprise_customers,
    get_enterprise_id_for_current_request_user_from_jwt,
    get_or_create_enterprise_customer_user,
    parse_consent_params,
    set_enterprise_customer_cookie,
    update_paginated_response
)
from ecommerce.extensions.partner.strategy import DefaultStrategy
from ecommerce.extensions.test.factories import (
    EnterpriseOfferFactory,
    EnterprisePercentageDiscountBenefitFactory,
    prepare_voucher
)
from ecommerce.tests.factories import PartnerFactory
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.applicator', 'Applicator')

TEST_ENTERPRISE_CUSTOMER_UUID = 'cf246b88-d5f6-4908-a522-fc307e0b0c59'


@ddt.ddt
class EnterpriseUtilsTests(EnterpriseServiceMockMixin, TestCase):
    def setUp(self):
        super(EnterpriseUtilsTests, self).setUp()
        self.learner = self.create_user(is_staff=True)
        self.client.login(username=self.learner.username, password=self.password)

    @responses.activate
    def test_get_enterprise_customers(self):
        """
        Verify that "get_enterprise_customers" returns an appropriate response from the
        "enterprise-customer" Enterprise service API endpoint.
        """
        self.mock_access_token_response()
        self.mock_enterprise_customer_list_api_get()
        response = get_enterprise_customers(self.request)
        self.assertEqual(response[0]['name'], "Enterprise Customer 1")
        self.assertEqual(response[1]['name'], "Enterprise Customer 2")

    @responses.activate
    def test_get_enterprise_customer(self):
        """
        Verify that "get_enterprise_customer" returns an appropriate response from the
        "enterprise-customer" Enterprise service API endpoint.
        """
        self.mock_access_token_response()
        self.mock_specific_enterprise_customer_api(TEST_ENTERPRISE_CUSTOMER_UUID)

        # verify the caching
        with patch.object(TieredCache, 'set_all_tiers', wraps=TieredCache.set_all_tiers) as mocked_set_all_tiers:
            mocked_set_all_tiers.assert_not_called()

            response = get_enterprise_customer(self.site, TEST_ENTERPRISE_CUSTOMER_UUID)
            self.assertEqual(TEST_ENTERPRISE_CUSTOMER_UUID, response.get('id'))
            self.assertEqual(mocked_set_all_tiers.call_count, 2)

            cached_response = get_enterprise_customer(self.site, TEST_ENTERPRISE_CUSTOMER_UUID)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)
            self.assertEqual(response, cached_response)

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
    @responses.activate
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

    @responses.activate
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

    @responses.activate
    def test_ecu_create_consent(self):
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
        self.mock_consent_post(**opts)
        self.assertEqual(create_enterprise_customer_user_consent(**kw), True)

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

    @responses.activate
    def test_get_enterprise_catalog(self):
        """
        Verify that "get_enterprise_catalog" returns an appropriate response from the
        "enterprise-catalog" Enterprise service API endpoint.
        """
        enterprise_catalog_uuid = str(uuid.uuid4())
        self.mock_access_token_response()
        self.mock_enterprise_catalog_api_get(enterprise_catalog_uuid)
        response = get_enterprise_catalog(self.site, enterprise_catalog_uuid, 50, 1)
        self.assertTrue(enterprise_catalog_uuid in response['next'])
        self.assertTrue(len(response['results']) == 3)
        for result in response['results']:
            self.assertTrue('course_runs' in result)

        cached_response = get_enterprise_catalog(self.site, enterprise_catalog_uuid, 50, 1)
        self.assertEqual(response, cached_response)

    @patch('ecommerce.enterprise.utils.get_decoded_jwt')
    def test_get_enterprise_id_for_current_request_user_from_jwt_request_has_no_jwt(self, mock_decode_jwt):
        """
        Verify get_enterprise_id_for_current_request_user_from_jwt returns None if
        decoded_jwt is None
        """
        mock_decode_jwt.return_value = None
        assert get_enterprise_id_for_current_request_user_from_jwt() is None

    @patch('ecommerce.enterprise.utils.get_decoded_jwt')
    def test_get_enterprise_id_for_current_request_user_from_jwt_request_has_jwt(self, mock_decode_jwt):
        """
        Verify get_enterprise_id_for_current_request_user_from_jwt returns jwt context
        for user if request has jwt and user has proper role
        """
        mock_decode_jwt.return_value = {
            'roles': ['{}:some-uuid'.format(SYSTEM_ENTERPRISE_LEARNER_ROLE)]
        }
        assert get_enterprise_id_for_current_request_user_from_jwt() == 'some-uuid'

    @patch('ecommerce.enterprise.utils.get_decoded_jwt')
    def test_get_enterprise_id_for_current_request_user_from_jwt_request_has_jwt_no_context(self, mock_decode_jwt):
        """
        Verify get_enterprise_id_for_current_request_user_from_jwt returns None if jwt
        context is missing
        """
        mock_decode_jwt.return_value = {
            'roles': ['{}'.format(SYSTEM_ENTERPRISE_LEARNER_ROLE)]
        }
        assert get_enterprise_id_for_current_request_user_from_jwt() is None

    @patch('ecommerce.enterprise.utils.get_decoded_jwt')
    def test_get_enterprise_id_for_current_request_user_from_jwt_request_has_jwt_non_learner(self, mock_decode_jwt):
        """
        Verify get_enterprise_id_for_current_request_user_from_jwt returns None if
        user role is incorrect
        """

        mock_decode_jwt.return_value = {
            'roles': ['{}:some-uuid'.format(SYSTEM_ENTERPRISE_ADMIN_ROLE)]
        }
        assert get_enterprise_id_for_current_request_user_from_jwt() is None

    @patch('ecommerce.enterprise.api.get_enterprise_id_for_current_request_user_from_jwt')
    def test_get_enterprise_id_for_user_enterprise_in_jwt(self, mock_get_jwt_uuid):
        """
        Verify get_enterprise_id_for_user returns ent id if uuid in jwt context
        """
        mock_get_jwt_uuid.return_value = 'my-uuid'
        assert get_enterprise_id_for_user('some-site', self.learner) == 'my-uuid'

    @responses.activate
    def test_get_enterprise_customer_catalogs(self):
        """
        Verify that "get_enterprise_customer_catalogs" works as expected with and without caching.
        """
        enterprise_customer_uuid = str(uuid.uuid4())
        base_url = self.LEGACY_ENTERPRISE_CATALOG_URL

        self.mock_access_token_response()
        self.mock_enterprise_catalog_api(enterprise_customer_uuid)

        # verify the caching
        with patch.object(TieredCache, 'set_all_tiers', wraps=TieredCache.set_all_tiers) as mocked_set_all_tiers:
            mocked_set_all_tiers.assert_not_called()

            response = get_enterprise_customer_catalogs(self.site, base_url, enterprise_customer_uuid, 1)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)

            cached_response = get_enterprise_customer_catalogs(self.site, base_url, enterprise_customer_uuid, 1)
            self.assertEqual(response, cached_response)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)

    @responses.activate
    def test_get_enterprise_customer_catalogs_with_exception(self):
        """
        Verify that "get_enterprise_customer_catalogs" return default response on exception.
        """
        enterprise_customer_uuid = str(uuid.uuid4())
        base_url = self.LEGACY_ENTERPRISE_CATALOG_URL

        self.mock_access_token_response()
        self.mock_enterprise_catalog_api(enterprise_customer_uuid, raise_exception=True)

        with patch('ecommerce.enterprise.utils.logging.exception') as mock_logger:
            response = get_enterprise_customer_catalogs(self.site, base_url, enterprise_customer_uuid, 1)
            self.assertEqual(response, CUSTOMER_CATALOGS_DEFAULT_RESPONSE)
            self.assertTrue(mock_logger.called)

    @ddt.data(
        {
            'next_url': None,
            'expected_next': None,
            'previous': None,
            'expected_previous': None,
        },
        {
            'next_url': None,
            'expected_next': None,
            'previous': 'http://lms.server/enterprise/api/v1/enterprise_catalogs/?enterprise=6ae013d4&page=3',
            'expected_previous': 'http://ecom.server/api/v2/enterprise/customer_catalogs?enterprise=6ae013d4&page=3',
        },
        {
            'next_url': 'http://lms.server/enterprise/api/v1/enterprise_catalogs/?enterprise=6ae013d4&page=3',
            'expected_next': 'http://ecom.server/api/v2/enterprise/customer_catalogs?enterprise=6ae013d4&page=3',
            'previous': None,
            'expected_previous': None,
        },
        {
            'next_url': 'http://lms.server/enterprise/api/v1/enterprise_catalogs/?enterprise=6ae013d4&page=3',
            'expected_next': 'http://ecom.server/api/v2/enterprise/customer_catalogs?enterprise=6ae013d4&page=3',
            'previous': 'http://lms.server/enterprise/api/v1/enterprise_catalogs/?enterprise=6ae013d4&page=1',
            'expected_previous': 'http://ecom.server/api/v2/enterprise/customer_catalogs?enterprise=6ae013d4&page=1',
        },
    )
    @ddt.unpack
    def test_update_paginated_response(self, next_url, expected_next, previous, expected_previous):
        """
        Verify that "update_paginated_response" util works as expected.
        """
        ecom_endpoint_url = 'http://ecom.server/api/v2/enterprise/customer_catalogs'
        original_response = dict(CUSTOMER_CATALOGS_DEFAULT_RESPONSE, next=next_url, previous=previous)

        updated_response = update_paginated_response(ecom_endpoint_url, original_response)

        expected_response = dict(
            original_response,
            next=expected_next,
            previous=expected_previous
        )
        self.assertEqual(expected_response, updated_response)

    @ddt.data(0, 100)
    @responses.activate
    def test_get_enterprise_customer_from_enterprise_offer(self, discount_value):
        """
        Verify that "get_enterprise_customer_from_enterprise_offer" returns `None` if expected conditions are not met.
        """
        course = CourseFactory(name='EnterpriseConsentErrorTest', partner=PartnerFactory())
        product = course.create_or_update_seat('verified', False, 50)

        benefit = EnterprisePercentageDiscountBenefitFactory(value=discount_value)
        offer = EnterpriseOfferFactory(benefit=benefit)
        # set wrong priority to invalidate the condition in util
        offer.priority = 111

        self.mock_enterprise_learner_api(
            learner_id=self.learner.id,
            enterprise_customer_uuid=str(offer.condition.enterprise_customer_uuid),
            course_run_id=course.id,
        )

        self.mock_catalog_contains_course_runs(
            [course.id],
            str(offer.condition.enterprise_customer_uuid),
            enterprise_customer_catalog_uuid=str(offer.condition.enterprise_customer_catalog_uuid),
            contains_content=True,
        )

        basket = BasketFactory(site=self.site, owner=self.create_user())
        basket.add_product(product)
        basket.strategy = DefaultStrategy()
        Applicator().apply_offers(basket, [offer])

        self.assertIsNone(get_enterprise_customer_from_enterprise_offer(basket))

    @patch('ecommerce.enterprise.utils.get_enterprise_customer')
    @ddt.data(
        ('edx', 'edx'),
        ('', 'edX Support Team'),
    )
    @ddt.unpack
    def test_get_enterprise_customer_sender_alias(self, sender_alias, expected_sender_alias, enterprise_customer):
        """
        Verify get_enterprise_customer_sender_alias returns enterprise sender alias if exists otherwise return default.
        """
        enterprise_customer.return_value = {'sender_alias': sender_alias}
        sender_alias = get_enterprise_customer_sender_alias('some-site', 'uuid')
        assert sender_alias == expected_sender_alias

    @patch('ecommerce.enterprise.utils.get_enterprise_customer')
    @ddt.data(
        ('edx@example.com', 'edx@example.com'),
        ('', ''),
    )
    @ddt.unpack
    def test_get_enterprise_customer_reply_to_email(self, reply_to, expected_reply_to, enterprise_customer):
        """
        Verify get_enterprise_customer_reply_to_email returns enterprise reply_to email/
        """
        enterprise_customer.return_value = {'reply_to': reply_to}
        reply_to = get_enterprise_customer_reply_to_email('some-site', 'uuid')
        self.assertEqual(reply_to, expected_reply_to)

    def test_parse_consent_params(self):
        """
        Verify that "parse_consent_params" util works as expected.
        """

        mock_request = RequestFactory().get(
            '/any?consent_url_param_string=left_sidebar_text_override%3D')
        parsed = parse_consent_params(mock_request)
        self.assertDictEqual(parsed, {'left_sidebar_text_override': ''})

        mock_request2 = RequestFactory().get('/any')
        parsed = parse_consent_params(mock_request2)
        assert parsed is None

    def test_find_active_enterprise_customer_user(self):
        """
        Verify `find_active_enterprise_customer_user` returns the enterprise customer user that is
        marked as `active=True`.
        """
        example_enterprise_customer_users = [
            {'id': 1, 'active': False},
            {'id': 2, 'active': True},
            {'id': 3, 'active': False},
        ]
        active_enterprise_customer_user = find_active_enterprise_customer_user(example_enterprise_customer_users)
        assert active_enterprise_customer_user['id'] == 2
