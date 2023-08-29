# -*- coding: utf-8 -*-
"""Broadly-useful mixins for use in automated tests."""


import datetime
import json
from decimal import Decimal
from unittest.mock import Mock

import responses
from crum import set_current_request
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.urls import reverse
from django.utils.timezone import now
from edx_django_utils.cache import TieredCache
from edx_rest_api_client.client import _get_oauth_url
from edx_rest_framework_extensions.auth.jwt.cookies import jwt_cookie_name
from edx_rest_framework_extensions.auth.jwt.tests.utils import (
    generate_jwt,
    generate_jwt_token,
    generate_unversioned_payload
)
from mock import patch
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from oscar.test.utils import RequestFactory
from social_django.models import UserSocialAuth
from threadlocals.threadlocals import set_thread_variable
from waffle.models import Flag

from ecommerce.core.constants import ALL_ACCESS_CONTEXT, SYSTEM_ENTERPRISE_ADMIN_ROLE, SYSTEM_ENTERPRISE_OPERATOR_ROLE
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.models import Course
from ecommerce.courses.utils import mode_for_product
from ecommerce.extensions.fulfillment.signals import SHIPPING_EVENT_NAME
from ecommerce.extensions.payment.helpers import get_default_processor_class, get_processor_class_by_name
from ecommerce.tests.factories import SiteConfigurationFactory, UserFactory

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Selector = get_class('partner.strategy', 'Selector')
ShippingEventType = get_model('order', 'ShippingEventType')
Order = get_model('order', 'Order')
Partner = get_model('partner', 'Partner')
ProductAttribute = get_model('catalogue', 'ProductAttribute')
ProductClass = get_model('catalogue', 'ProductClass')
User = get_user_model()
Voucher = get_model('voucher', 'Voucher')

CONTENT_TYPE = 'application/json'


class UserMixin:
    """Provides utility methods for creating and authenticating users in test cases."""
    access_token = 'test-access-token'
    user_id = 'test-user-id'
    password = 'test'
    lms_user_id = 12321

    def create_user(self, lms_user_id=lms_user_id, **kwargs):
        """Create a user, with overrideable defaults."""
        not_provided = object()
        if kwargs.get('username', not_provided) is None:
            kwargs.pop('username')
        return UserFactory(password=self.password, lms_user_id=lms_user_id, **kwargs)

    def create_access_token(self, user, access_token=None):
        """
        Create an OAuth access token for the specified user.

        If no access_token value is supplied, the default (self.access_token) will be used.
        """
        access_token = access_token or self.access_token
        UserSocialAuth.objects.create(user=user, extra_data={'access_token': access_token})

    def set_user_id_in_social_auth(self, user, user_id=None):
        """
        Sets the user_id in social auth for the specified user.

        If no user_id value is supplied, the default (self.user_id) will be used.
        """
        user_id = user_id or self.user_id
        UserSocialAuth.objects.create(user=user, extra_data={'user_id': user_id})

    def generate_jwt_token_header(self, user):
        """Generate a valid JWT token header for authenticated requests."""
        return "JWT {token}".format(token=generate_jwt(user))


class ThrottlingMixin:
    """Provides utility methods for test cases validating the behavior of rate-limited endpoints."""

    def setUp(self):
        super(ThrottlingMixin, self).setUp()

        # Throttling for tests relies on the cache. To get around throttling, simply clear the cache.
        self.addCleanup(TieredCache.dangerous_clear_all_tiers)


class JwtMixin:
    """ Mixin with JWT-related helper functions. """
    JWT_SECRET_KEY = settings.JWT_AUTH['JWT_ISSUERS'][0]['SECRET_KEY']
    issuer = settings.JWT_AUTH['JWT_ISSUERS'][0]['ISSUER']

    def generate_token(self, payload, secret=None):
        """Generate a JWT token with the provided payload."""
        secret = secret or self.JWT_SECRET_KEY
        return generate_jwt_token(payload, secret)

    def set_jwt_cookie(self, system_wide_role=SYSTEM_ENTERPRISE_ADMIN_ROLE, context='some_context'):
        """
        Set jwt token in cookies
        """
        role_data = '{system_wide_role}'.format(system_wide_role=system_wide_role)
        if context is not None:
            role_data += ':{context}'.format(context=context)

        payload = generate_unversioned_payload(self.user)
        payload.update({
            'roles': [role_data]
        })
        jwt_token = generate_jwt_token(payload)

        self.client.cookies[jwt_cookie_name()] = jwt_token

    def generate_new_user_token(self, username, email, is_staff):
        """
        Generates a JWT token for a user with provided attributes.

        Note: Doesn't actually create the user object, so it can be created
            during JWT authentication.
        """
        # create a mock user, and not the actual user, because we want to confirm that
        #   the user is created during JWT authentication
        user = Mock()
        user.username = username
        user.email = email
        user.is_staff = is_staff

        payload = generate_unversioned_payload(user)
        # At this time, generate_unversioned_payload isn't setting 'administrator', but
        #   it should.
        payload['administrator'] = is_staff
        return self.generate_token(payload)


class BasketCreationMixin(UserMixin, JwtMixin):
    """Provides utility methods for creating baskets in test cases."""
    PATH = reverse('api:v2:baskets:create')
    FREE_SKU = 'FREE_PRODUCT'

    def setUp(self):
        super(BasketCreationMixin, self).setUp()

        self.user = self.create_user()

        product_class = factories.ProductClassFactory(
            name=u'Áutomobilé',
            requires_shipping=False,
            track_stock=False
        )
        self.base_product = factories.ProductFactory(
            structure='parent',
            title=u'Lamborghinï Gallardœ',
            product_class=product_class,
            stockrecords=None,
        )
        self.free_product = factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title='Cardboard Cutout',
            stockrecords__partner_sku=self.FREE_SKU,
            stockrecords__price_excl_tax=Decimal('0.00'),
        )
        self.set_jwt_cookie(SYSTEM_ENTERPRISE_OPERATOR_ROLE, ALL_ACCESS_CONTEXT)

    def create_basket(self, skus=None, checkout=None, payment_processor_name=None, auth=True, token=None):
        """Issue a POST request to the basket creation endpoint."""
        request_data = {}
        if skus:
            request_data['products'] = []
            for sku in skus:
                request_data['products'].append({'sku': sku})

        if checkout:
            request_data['checkout'] = checkout

        if payment_processor_name:
            request_data['payment_processor_name'] = payment_processor_name

        if auth:
            response = self.client.post(
                self.PATH,
                data=json.dumps(request_data),
                content_type=CONTENT_TYPE,
                HTTP_AUTHORIZATION='JWT {}'.format(token) if token else self.generate_jwt_token_header(self.user)
            )
        else:
            response = self.client.post(
                self.PATH,
                data=json.dumps(request_data),
                content_type=CONTENT_TYPE
            )

        return response

    def assert_successful_basket_creation(
            self, skus=None, checkout=None, payment_processor_name=None, requires_payment=False
    ):
        """Verify that basket creation succeeded."""
        # Ideally, we'd use Oscar's ShippingEventTypeFactory here, but it's not exposed/public.
        ShippingEventType.objects.get_or_create(name=SHIPPING_EVENT_NAME)

        with patch('ecommerce.extensions.api.v2.views.baskets.audit_log') as mock_audit_log:
            response = self.create_basket(skus=skus, checkout=checkout, payment_processor_name=payment_processor_name)

            self.assertEqual(response.status_code, 200)

            basket = Basket.objects.get()
            basket.strategy = Selector().strategy(user=self.user)
            self.assertEqual(response.data['id'], basket.id)

            if checkout:
                mock_audit_log.assert_called_with(
                    'basket_frozen',
                    amount=basket.total_excl_tax,
                    basket_id=basket.id,
                    currency=basket.currency,
                    user_id=basket.owner.id
                )

                if requires_payment:
                    self.assertIsNone(response.data['order'])
                    self.assertIsNotNone(response.data['payment_data']['payment_processor_name'])
                    self.assertIsNotNone(response.data['payment_data']['payment_form_data'])
                    if payment_processor_name is None:
                        processor_class = get_default_processor_class()
                    else:
                        processor_class = get_processor_class_by_name(payment_processor_name)
                    assert (
                        response.data['payment_data']['payment_page_url'] ==
                        processor_class(Site.objects.all()[0]).client_side_payment_url
                    )
                else:
                    self.assertEqual(response.data['order']['number'], Order.objects.get().number)
                    self.assertIsNone(response.data['payment_data'])
            else:
                self.assertIsNone(response.data['order'])
                self.assertIsNone(response.data['payment_data'])


class BusinessIntelligenceMixin:
    """Provides assertions for test cases validating the emission of business intelligence events."""

    def assert_correct_event(
            self, mock_track, instance, expected_user_id, expected_client_id, expected_ip, order_number, currency,
            email, total, revenue, coupon=None, discount=Decimal('0.00'), check_traits=None
    ):
        """Check that the tracking context was correctly reflected in the emitted event."""
        (event_user_id, event_name, event_payload), kwargs = mock_track.call_args
        self.assertEqual(event_user_id, expected_user_id)
        self.assertEqual(event_name, 'Order Completed')
        expected_context = {
            'ip': expected_ip,
            'Google Analytics': {'clientId': expected_client_id},
            'page': {'url': 'https://testserver.fake/'},
        }
        # TODO: This bit of testing is required only as long as we are routing
        # Order Completed events to Hubspot and should be removed/cleaned up as part of
        # DENG-797
        if check_traits:
            context_without_traits = {k: v for k, v in kwargs['context'].items() if k != 'traits'}
            self.assertEqual(context_without_traits, expected_context)
            # Verify that the event payload is duplicated in the `traits` subsection of
            # the event `context`.
            traits = kwargs['context']['traits']
            self.assert_correct_event_payload(
                instance, traits, order_number, currency, email, total, revenue,
                coupon, discount
            )
        else:
            self.assertEqual(kwargs['context'], expected_context)
        self.assert_correct_event_payload(
            instance, event_payload, order_number, currency, email, total, revenue, coupon, discount
        )

    def assert_correct_event_payload(
            self, instance, event_payload, order_number, currency, email, total, revenue,
            coupon, discount
    ):
        """
        Check that field values in the event payload correctly represent the
        completed order or refund.
        """
        self.assertEqual(
            ['coupon', 'currency', 'discount', 'email', 'orderId', 'processor_name', 'products', 'revenue',
             'stripe_enabled', 'total'],
            sorted(event_payload.keys())
        )
        self.assertEqual(event_payload['orderId'], order_number)
        self.assertEqual(event_payload['currency'], currency)
        self.assertEqual(event_payload['coupon'], coupon)
        self.assertEqual(event_payload['discount'], discount)
        self.assertEqual(event_payload['email'], email)

        lines = instance.lines.all()
        self.assertEqual(len(lines), len(event_payload['products']))

        model_name = instance.__class__.__name__
        tracked_products_dict = {product['id']: product for product in event_payload['products']}

        if model_name == 'Order':
            self.assertEqual(event_payload['total'], float(total))
            self.assertEqual(event_payload['revenue'], float(revenue))
            # value of revenue field should be the same as total.
            self.assertEqual(event_payload['revenue'], float(total))

            for line in lines:
                tracked_product = tracked_products_dict.get(line.partner_sku)
                self.assertIsNotNone(tracked_product)
                self.assertEqual(line.product.course.id, tracked_product['name'])
                self.assertEqual(float(line.line_price_excl_tax), tracked_product['price'])
                self.assertEqual(line.quantity, tracked_product['quantity'])
                self.assertEqual(mode_for_product(line.product), tracked_product['sku'])
                self.assertEqual(line.product.get_product_class().name, tracked_product['category'])
        else:
            # Payload validation is currently limited to order and refund events
            self.fail()


class SiteMixin:
    def setUp(self):
        super(SiteMixin, self).setUp()

        # Set the domain used for all test requests
        domain = 'testserver.fake'
        self.client = self.client_class(SERVER_NAME=domain)

        Course.objects.all().delete()
        Partner.objects.all().delete()
        Site.objects.all().delete()
        lms_url_root = "http://lms.testserver.fake"
        self.site_configuration = SiteConfigurationFactory(
            lms_url_root=lms_url_root,
            from_email='from@example.com',
            oauth_settings={
                'SOCIAL_AUTH_EDX_OAUTH2_KEY': 'key',
                'SOCIAL_AUTH_EDX_OAUTH2_SECRET': 'secret',
                'BACKEND_SERVICE_EDX_OAUTH2_KEY': 'key',
                'BACKEND_SERVICE_EDX_OAUTH2_SECRET': 'secret',
                'SOCIAL_AUTH_EDX_OAUTH2_LOGOUT_URL': lms_url_root + '/logout',
            },
            partner__name='edX',
            partner__short_code='edx',
            segment_key='fake_segment_key',
            site__domain=domain,
            site__id=settings.SITE_ID,
            base_cookie_domain=domain,
        )
        self.partner = self.site_configuration.partner
        self.partner.default_site = self.site = self.site_configuration.site
        self.partner.save()

        self.request = RequestFactory(SERVER_NAME=domain).get('')
        self.request.session = None
        self.request.site = self.site
        set_thread_variable('request', self.request)
        set_current_request(self.request)
        self.addCleanup(set_current_request)

    def mock_access_token_response(self, status=200, **token_data):
        """ Mock the response from the OAuth provider's access token endpoint. """
        url = _get_oauth_url(settings.BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL)

        token = 'abc123'
        data = {
            'access_token': token,
            'expires_in': 3600,
        }
        data.update(token_data)
        responses.add(responses.POST, url, json=data, content_type=CONTENT_TYPE, status=status)

        return token


class TestServerUrlMixin:
    def get_full_url(self, path, site=None):
        """ Returns a complete URL with the given path. """
        site = site or self.site
        return 'http://{domain}{path}'.format(domain=site.domain, path=path)


class ApiMockMixin:
    """ Common Mocks for the API responses. """

    def mock_api_error(self, error, url):

        responses.add(responses.GET, url, body=error, content_type=CONTENT_TYPE)


class LmsApiMockMixin:
    """ Mocks for the LMS API responses. """

    def mock_course_api_response(self, course=None):
        """ Helper function to register an API endpoint for the course information. """
        course_info = {
            'short_description': 'Test description',
            'media': {
                'course_image': {
                    'uri': '/asset-v1:test+test+test+type@asset+block@images_course_image.jpg'
                },
                'image': {
                    'raw': 'path/to/the/course/image'
                }
            },
            'start': '2013-02-05T05:00:00Z',
            'name': course.name if course else 'Test course',
            'org': 'test'
        }
        course_id = course.id if course else 'course-v1:test+test+test'
        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(course_id))
        responses.add(responses.GET, course_url, json=course_info, content_type=CONTENT_TYPE)

    def mock_account_api(self, request, username, data):
        """ Mock the account LMS API endpoint for a user.

        Args:
            request (WSGIRequest): The request from which the host URL is constructed.
            username (string): The username of the user.
            data (dict): Dictionary of data the account API should return.
        """
        url = '{host}/accounts/{username}'.format(
            host=request.site.siteconfiguration.build_lms_url('/api/user/v1'),
            username=username,
        )
        responses.add(responses.GET, url, json=data, content_type=CONTENT_TYPE)

    def mock_bulk_lms_users_using_emails(self, request, users):
        """ Mock the account Bulk LMS API endpoint for users.

        Args:
            request (WSGIRequest): The request from which the host URL is constructed.
            users(list): list of users(dicts) to mock.
        """
        url = '{host}/accounts/search_emails'.format(
            host=request.site.siteconfiguration.build_lms_url('/api/user/v1'),
        )
        data = [{
            'id': user['lms_user_id'],
            'username': user['username'],
            'email': user['email'],
        } for user in users]
        responses.add(responses.POST, url, json=data, content_type=CONTENT_TYPE)

    def mock_eligibility_api(self, request, user, course_key, eligible=True):
        """ Mock eligibility API endpoint. Returns eligibility data. """
        eligibility_data = [{
            'username': user.username,
            'course_key': course_key,
            'deadline': str(datetime.datetime.now() + datetime.timedelta(days=1))
        }] if eligible else []
        url = '{host}/eligibility/?username={username}&course_key={course_key}'.format(
            host=request.site.siteconfiguration.build_lms_url('/api/credit/v1'),
            username=user.username,
            course_key=course_key.replace("+", "%2B")
        )
        responses.add(responses.GET, url, json=eligibility_data, content_type=CONTENT_TYPE)

    @staticmethod
    def get_default_expiration():
        return (now() + datetime.timedelta(days=1)).isoformat()

    def mock_deactivation_api(self, request, username, response):
        """ Mock deactivation API endpoint. """
        url = '{host}/accounts/{username}/deactivate/'.format(
            host=request.site.siteconfiguration.build_lms_url('/api/user/v1'),
            username=username
        )
        responses.add(
            responses.POST,
            url,
            body=response() if callable(response) else response,
            content_type=CONTENT_TYPE
        )


class TestWaffleFlagMixin:
    """ Updates or creates a waffle flag and activates to True. Turns on any waffle flag to all tests
    without requiring the addition of the flag in individual methods/classes """
    def setUp(self):
        super(TestWaffleFlagMixin, self).setUp()
        # Note: if you are adding a waffle flag and need to have unit tests
        # run with the flag on, import and add the flag to the list below.
        # Note 2: Flags should be temporary, pls link the ticket to remove
        # the flag from this mixin with the PR that added the flag.
        waffle_flags_list = []
        for flag_name in waffle_flags_list:
            Flag.objects.update_or_create(name=flag_name, defaults={'everyone': True})
