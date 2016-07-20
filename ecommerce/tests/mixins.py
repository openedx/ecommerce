# -*- coding: utf-8 -*-
"""Broadly-useful mixins for use in automated tests."""
import json
from decimal import Decimal

import httpretty
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
from mock import patch
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from social.apps.django_app.default.models import UserSocialAuth
from threadlocals.threadlocals import set_thread_variable

from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.fulfillment.signals import SHIPPING_EVENT_NAME
from ecommerce.tests.factories import SiteConfigurationFactory

Applicator = get_class('offer.utils', 'Applicator')
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


class APIMixin(object):
    """Provides utility methods for API endpoint test cases."""

    def get_response_json(self, method, path, data=None):
        """Helper method for sending requests and returning JSON response content."""
        if method == 'GET':
            response = self.client.get(path)
        elif method == 'POST':
            response = self.client.post(path, json.dumps(data), 'application/json')
        elif method == 'PUT':
            response = self.client.put(path, json.dumps(data), 'application/json')
        return json.loads(response.content), response.status_code


class ApiMockMixin(object):
    """ Common Mocks for the API responses. """

    def setUp(self):
        super(ApiMockMixin, self).setUp()

    def mock_api_error(self, error, url):
        def callback(request, uri, headers):  # pylint: disable=unused-argument
            raise error
        httpretty.register_uri(httpretty.GET, url, body=callback, content_type='application/json')


class BusinessIntelligenceMixin(object):
    """Provides assertions for test cases validating the emission of business intelligence events."""

    def assert_correct_event(
            self, mock_track, instance, expected_user_id, expected_client_id, expected_ip, order_number, currency, total
    ):
        """Check that the tracking context was correctly reflected in the emitted event."""
        (event_user_id, event_name, event_payload), kwargs = mock_track.call_args
        self.assertEqual(event_user_id, expected_user_id)
        self.assertEqual(event_name, 'Completed Order')
        self.assertEqual(kwargs['context'], {'ip': expected_ip, 'Google Analytics': {'clientId': expected_client_id}})
        self.assert_correct_event_payload(instance, event_payload, order_number, currency, total)

    def assert_correct_event_payload(self, instance, event_payload, order_number, currency, total):
        """
        Check that field values in the event payload correctly represent the
        completed order or refund.
        """
        self.assertEqual(['currency', 'orderId', 'products', 'total'], sorted(event_payload.keys()))
        self.assertEqual(event_payload['orderId'], order_number)
        self.assertEqual(event_payload['currency'], currency)

        lines = instance.lines.all()
        self.assertEqual(len(lines), len(event_payload['products']))

        model_name = instance.__class__.__name__
        tracked_products_dict = {product['id']: product for product in event_payload['products']}

        if model_name == 'Order':
            self.assertEqual(event_payload['total'], str(total))

            for line in lines:
                tracked_product = tracked_products_dict.get(line.partner_sku)
                self.assertIsNotNone(tracked_product)
                self.assertEqual(line.product.course.id, tracked_product['name'])
                self.assertEqual(str(line.line_price_excl_tax), tracked_product['price'])
                self.assertEqual(line.quantity, tracked_product['quantity'])
                self.assertEqual(mode_for_seat(line.product), tracked_product['sku'])
                self.assertEqual(line.product.get_product_class().name, tracked_product['category'])
        elif model_name == 'Refund':
            self.assertEqual(event_payload['total'], '-{}'.format(total))

            for line in lines:
                tracked_product = tracked_products_dict.get(line.order_line.partner_sku)
                self.assertIsNotNone(tracked_product)
                self.assertEqual(line.order_line.product.course.id, tracked_product['name'])
                self.assertEqual(str(line.line_credit_excl_tax), tracked_product['price'])
                self.assertEqual(-1 * line.quantity, tracked_product['quantity'])
                self.assertEqual(mode_for_seat(line.order_line.product), tracked_product['sku'])
                self.assertEqual(line.order_line.product.get_product_class().name, tracked_product['category'])
        else:
            # Payload validation is currently limited to order and refund events
            self.fail()


class JwtMixin(object):
    """ Mixin with JWT-related helper functions. """
    JWT_SECRET_KEY = settings.JWT_AUTH['JWT_SECRET_KEY']
    issuer = settings.JWT_AUTH['JWT_ISSUERS'][0]

    def generate_token(self, payload, secret=None):
        """Generate a JWT token with the provided payload."""
        secret = secret or self.JWT_SECRET_KEY
        token = jwt.encode(dict(payload, iss=self.issuer), secret)
        return token


class LmsApiMockMixin(object):
    """ Mocks for the LMS API reponses. """

    def setUp(self):
        super(LmsApiMockMixin, self).setUp()

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
        course_info_json = json.dumps(course_info)
        course_id = course.id if course else 'course-v1:test+test+test'
        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(course_id))
        httpretty.register_uri(httpretty.GET, course_url, body=course_info_json, content_type='application/json')

    def mock_enrollment_api(self, request, user, course_id, is_active=True, mode='audit'):
        """ Returns a successful response indicating self.user is enrolled in the specified course mode. """
        url = '{host}/enrollment/{username},{course_id}'.format(
            host=request.site.siteconfiguration.build_lms_url('/api/enrollment/v1'),
            username=user.username,
            course_id=course_id
        )
        body = json.dumps({'mode': mode, 'is_active': is_active})
        httpretty.register_uri(httpretty.GET, url, body=body, content_type='application/json')

    def mock_enrollment_api_error(self, request, user, course_id, error):
        """ Mock Enrollment api call which raises error when called """
        def callback(request, uri, headers):  # pylint: disable=unused-argument
            raise error

        url = '{host}/enrollment/{username},{course_id}'.format(
            host=request.site.siteconfiguration.build_lms_url('/api/enrollment/v1'),
            username=user.username,
            course_id=course_id
        )
        httpretty.register_uri(httpretty.GET, url, body=callback, content_type='application/json')


class SiteMixin(object):
    def setUp(self):
        super(SiteMixin, self).setUp()

        # Set the domain used for all test requests
        domain = 'testserver.fake'
        self.client = self.client_class(SERVER_NAME=domain)

        Site.objects.all().delete()
        site_configuration = SiteConfigurationFactory(
            partner__name='edX',
            site__id=settings.SITE_ID,
            site__domain=domain,
            segment_key='fake_segment_key',
            oauth_settings={
                'SOCIAL_AUTH_EDX_OIDC_KEY': 'key',
                'SOCIAL_AUTH_EDX_OIDC_SECRET': 'secret'
            }
        )
        self.partner = site_configuration.partner
        self.site = site_configuration.site

        self.request = RequestFactory().get('')
        self.request.session = None
        self.request.site = self.site
        set_thread_variable('request', self.request)


class TestServerUrlMixin(object):
    def get_full_url(self, path, site=None):
        """ Returns a complete URL with the given path. """
        site = site or self.site
        return 'http://{domain}{path}'.format(domain=site.domain, path=path)


class ThrottlingMixin(object):
    """Provides utility methods for test cases validating the behavior of rate-limited endpoints."""

    def setUp(self):
        super(ThrottlingMixin, self).setUp()

        # Throttling for tests relies on the cache. To get around throttling, simply clear the cache.
        self.addCleanup(cache.clear)


class UserMixin(object):
    """Provides utility methods for creating and authenticating users in test cases."""
    access_token = 'test-access-token'
    password = 'test'

    def create_user(self, **kwargs):
        """Create a user, with overrideable defaults."""
        return factories.UserFactory(password=self.password, **kwargs)

    def create_access_token(self, user, access_token=None):
        """
        Create an OAuth access token for the specified user.

        If no access_token value is supplied, the default (self.access_token) will be used.
        """
        access_token = access_token or self.access_token
        UserSocialAuth.objects.create(user=user, extra_data={'access_token': access_token})

    def generate_jwt_token_header(self, user, secret=None):
        """Generate a valid JWT token header for authenticated requests."""
        secret = secret or settings.JWT_AUTH['JWT_SECRET_KEY']
        payload = {
            'username': user.username,
            'email': user.email,
            'iss': settings.JWT_AUTH['JWT_ISSUERS'][0]
        }
        return "JWT {token}".format(token=jwt.encode(payload, secret))

    def create_and_login_user(self, is_staff=True):
        """ Create a user and use its credentials to login. """
        self.user = self.create_user(is_staff=is_staff)
        self.client.login(username=self.user.username, password=self.password)


class BasketCreationMixin(UserMixin, JwtMixin):
    """Provides utility methods for creating baskets in test cases."""
    PATH = reverse('api:v2:baskets:create')
    FREE_SKU = u'𝑭𝑹𝑬𝑬-𝑷𝑹𝑶𝑫𝑼𝑪𝑻'

    def setUp(self):
        super(BasketCreationMixin, self).setUp()

        self.user = self.create_user()

        product_class = factories.ProductClassFactory(
            name=u'𝑨𝒖𝒕𝒐𝒎𝒐𝒃𝒊𝒍𝒆',
            requires_shipping=False,
            track_stock=False
        )
        self.base_product = factories.ProductFactory(
            structure='parent',
            title=u'𝑳𝒂𝒎𝒃𝒐𝒓𝒈𝒉𝒊𝒏𝒊 𝑮𝒂𝒍𝒍𝒂𝒓𝒅𝒐',
            product_class=product_class,
            stockrecords=None,
        )
        self.free_product = factories.ProductFactory(
            structure='child',
            parent=self.base_product,
            title=u'𝑪𝒂𝒓𝒅𝒃𝒐𝒂𝒓𝒅 𝑪𝒖𝒕𝒐𝒖𝒕',
            stockrecords__partner_sku=self.FREE_SKU,
            stockrecords__price_excl_tax=Decimal('0.00'),
        )

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
                content_type='application/json',
                HTTP_AUTHORIZATION='JWT {}'.format(token) if token else self.generate_jwt_token_header(self.user)
            )
        else:
            response = self.client.post(
                self.PATH,
                data=json.dumps(request_data),
                content_type='application/json'
            )

        return response

    def assert_successful_basket_creation(
            self, skus=None, checkout=None, payment_processor_name=None, requires_payment=False
    ):
        """Verify that basket creation succeeded."""
        # Ideally, we'd use Oscar's ShippingEventTypeFactory here, but it's not exposed/public.
        ShippingEventType.objects.get_or_create(name=SHIPPING_EVENT_NAME)

        with patch('ecommerce.extensions.analytics.utils.audit_log') as mock_audit_log:
            response = self.create_basket(skus=skus, checkout=checkout, payment_processor_name=payment_processor_name)

            self.assertEqual(response.status_code, 200)

            basket = Basket.objects.get()
            basket.strategy = Selector().strategy(user=self.user)
            self.assertEqual(response.data['id'], basket.id)

            if checkout:
                self.assertTrue(mock_audit_log.called_with(
                    'basket_frozen',
                    amount=basket.total_excl_tax,
                    basket_id=basket.id,
                    currency=basket.currency,
                    user_id=basket.owner.id
                ))

                if requires_payment:
                    self.assertIsNone(response.data['order'])
                    self.assertIsNotNone(response.data['payment_data']['payment_processor_name'])
                    self.assertIsNotNone(response.data['payment_data']['payment_form_data'])
                    self.assertIsNotNone(response.data['payment_data']['payment_page_url'])
                else:
                    self.assertEqual(response.data['order']['number'], Order.objects.get().number)
                    self.assertIsNone(response.data['payment_data'])
            else:
                self.assertIsNone(response.data['order'])
                self.assertIsNone(response.data['payment_data'])
