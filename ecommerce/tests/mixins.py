# -*- coding: utf-8 -*-
"""Broadly-useful mixins for use in automated tests."""
import datetime
from decimal import Decimal
import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
import httpretty
import jwt
from mock import patch
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from threadlocals.threadlocals import set_thread_variable
from social.apps.django_app.default.models import UserSocialAuth

from ecommerce.core.models import BusinessClient
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.utils import mode_for_seat
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.fulfillment.signals import SHIPPING_EVENT_NAME
from ecommerce.tests.factories import PartnerFactory, SiteConfigurationFactory

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


class ThrottlingMixin(object):
    """Provides utility methods for test cases validating the behavior of rate-limited endpoints."""

    def setUp(self):
        super(ThrottlingMixin, self).setUp()

        # Throttling for tests relies on the cache. To get around throttling, simply clear the cache.
        self.addCleanup(cache.clear)


class JwtMixin(object):
    """ Mixin with JWT-related helper functions. """
    JWT_SECRET_KEY = settings.JWT_AUTH['JWT_SECRET_KEY']
    issuer = settings.JWT_AUTH['JWT_ISSUERS'][0]

    def generate_token(self, payload, secret=None):
        """Generate a JWT token with the provided payload."""
        secret = secret or self.JWT_SECRET_KEY
        token = jwt.encode(dict(payload, iss=self.issuer), secret)
        return token


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
            request_data[AC.KEYS.PRODUCTS] = []
            for sku in skus:
                request_data[AC.KEYS.PRODUCTS].append({AC.KEYS.SKU: sku})

        if checkout:
            request_data[AC.KEYS.CHECKOUT] = checkout

        if payment_processor_name:
            request_data[AC.KEYS.PAYMENT_PROCESSOR_NAME] = payment_processor_name

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
                    self.assertIsNone(response.data[AC.KEYS.ORDER])
                    self.assertIsNotNone(response.data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_PROCESSOR_NAME])
                    self.assertIsNotNone(response.data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_FORM_DATA])
                    self.assertIsNotNone(response.data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_PAGE_URL])
                else:
                    self.assertEqual(response.data[AC.KEYS.ORDER][AC.KEYS.ORDER_NUMBER], Order.objects.get().number)
                    self.assertIsNone(response.data[AC.KEYS.PAYMENT_DATA])
            else:
                self.assertIsNone(response.data[AC.KEYS.ORDER])
                self.assertIsNone(response.data[AC.KEYS.PAYMENT_DATA])


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


class SiteMixin(object):
    def setUp(self):
        super(SiteMixin, self).setUp()

        # Set the domain used for all test requests
        domain = 'testserver.fake'
        self.client = self.client_class(SERVER_NAME=domain)

        Site.objects.get_current().delete()
        site_configuration = SiteConfigurationFactory(
            partner__name='edX',
            site__id=settings.SITE_ID,
            site__domain=domain,
            segment_key='fake_segment_key'
        )
        self.partner = site_configuration.partner
        self.site = site_configuration.site

        request = RequestFactory().get('')
        request.session = None
        request.site = self.site
        set_thread_variable('request', request)


class TestServerUrlMixin(object):
    def get_full_url(self, path, site=None):
        """ Returns a complete URL with the given path. """
        site = site or self.site
        return 'http://{domain}{path}'.format(domain=site.domain, path=path)


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
                }
            },
            'name': course.name if course else 'Test course',
            'org': 'test'
        }
        course_info_json = json.dumps(course_info)
        course_id = course.id if course else 'course-v1:test+test+test'
        course_url = get_lms_url('api/courses/v1/courses/{}/'.format(course_id))
        httpretty.register_uri(httpretty.GET, course_url, body=course_info_json, content_type='application/json')

    def mock_footer_api_response(self):
        """ Helper function to register an API endpoint for the footer information. """
        footer_url = get_lms_url('api/branding/v1/footer')
        footer_content = {
            'footer': 'edX Footer'
        }
        content_json = json.dumps(footer_content)
        httpretty.register_uri(httpretty.GET, footer_url, body=content_json, content_type='application/json')


class CouponMixin(object):
    """ Mixin for preparing data for coupons and creating coupons. """

    REDEMPTION_URL = "/coupons/offer/?code={}"

    def setUp(self):
        super(CouponMixin, self).setUp()
        self.category = factories.CategoryFactory()

        # Force the creation of a coupon ProductClass
        self.coupon_product_class  # pylint: disable=pointless-statement

    @property
    def coupon_product_class(self):
        defaults = {'requires_shipping': False, 'track_stock': False, 'name': 'Coupon'}
        pc, created = ProductClass.objects.get_or_create(slug='coupon', defaults=defaults)

        if created:
            factories.ProductAttributeFactory(
                code='coupon_vouchers',
                name='Coupon vouchers',
                product_class=pc,
                type='entity'
            )
            factories.ProductAttributeFactory(
                code='note',
                name='Note',
                product_class=pc,
                type='text'
            )

        return pc

    def create_coupon(
            self,
            title='Test coupon',
            price=100,
            client=None,
            partner=None,
            catalog=None,
            code='',
            benefit_value=100,
            note=None,
            max_uses=None,
            quantity=5
    ):
        """Helper method for creating a coupon.

        Arguments:
            title(str): Title of the coupon
            price(int): Price of the coupon
            partner(Partner): Partner used for creating a catalog
            catalog(Catalog): Catalog of courses for which the coupon applies
            code(str): Custom coupon code
            benefit_value(int): The voucher benefit value

        Returns:
            coupon (Coupon)

        """
        if partner is None:
            partner = PartnerFactory(name='Tester')
        if client is None:
            client, __ = BusinessClient.objects.get_or_create(name='Test Client')
        if catalog is None:
            catalog = Catalog.objects.create(partner=partner)
        if code is not '':
            quantity = 1
        data = {
            'partner': partner,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': benefit_value,
            'catalog': catalog,
            'end_date': datetime.date(2020, 1, 1),
            'code': code,
            'quantity': quantity,
            'start_date': datetime.date(2015, 1, 1),
            'voucher_type': Voucher.SINGLE_USE,
            'categories': [self.category],
            'note': note,
            'max_uses': max_uses,
        }

        coupon = CouponViewSet().create_coupon_product(
            title=title,
            price=price,
            data=data
        )

        request = RequestFactory()
        request.site = self.site
        request.user = factories.UserFactory()

        self.basket = prepare_basket(request, coupon)

        self.response_data = CouponViewSet().create_order_for_invoice(self.basket, coupon_id=coupon.id, client=client)
        coupon.client = client

        return coupon

    def apply_voucher(self, user, site, voucher):
        """ Apply the voucher to a basket. """
        basket = factories.BasketFactory(owner=user, site=site)
        product = voucher.offers.first().benefit.range.all_products()[0]
        basket.add_product(product)
        basket.vouchers.add(voucher)
        Applicator().apply(basket, self.user)
        return basket
