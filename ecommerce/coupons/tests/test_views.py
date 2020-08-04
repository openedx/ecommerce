# -*- coding: utf-8 -*-


import datetime
import urllib
from decimal import Decimal

import ddt
import httpretty
import mock
import pytz
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.timezone import now
from factory.fuzzy import FuzzyText
from oscar.core.loading import get_class, get_model
from oscar.test.factories import OrderFactory, OrderLineFactory, ProductFactory, RangeFactory, VoucherFactory

from ecommerce.core.url_utils import get_lms_url
from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.coupons.views import voucher_is_valid
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.enterprise.utils import (
    get_enterprise_course_consent_url,
    get_enterprise_customer_data_sharing_consent_token
)
from ecommerce.extensions.api.serializers import CouponCodeAssignmentSerializer
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder
from ecommerce.extensions.payment.models import EnterpriseContractMetadata
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.mixins import ApiMockMixin, LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Course = get_model('courses', 'Course')
Product = get_model('catalogue', 'Product')
Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
OrderLineVouchers = get_model('voucher', 'OrderLineVouchers')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
VoucherApplication = get_model('voucher', 'VoucherApplication')

CONTENT_TYPE = 'application/json'
COUPON_CODE = 'COUPONTEST'
ENTERPRISE_CUSTOMER = 'cf246b88-d5f6-4908-a522-fc307e0b0c59'
ENTERPRISE_CUSTOMER_CATALOG = 'abc18838-adcb-41d5-abec-b28be5bfcc13'


def format_url(base='', path='', params=None):
    if params:
        return '{base}{path}?{params}'.format(base=base, path=path, params=urllib.parse.urlencode(params))
    return '{base}{path}'.format(base=base, path=path)


class CouponAppViewTests(TestCase):
    path = reverse('coupons:app', args=[''])

    def test_login_required(self):
        """ Users are required to login before accessing the view. """
        self.client.logout()
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.url)

    def assert_response_status(self, is_staff, status_code):
        """Create a user and assert the status code from the response for that user."""
        user = self.create_user(is_staff=is_staff)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, status_code)

    def test_staff_user_required(self):
        """ Verify the view is only accessible to staff users. """
        self.assert_response_status(is_staff=False, status_code=404)
        self.assert_response_status(is_staff=True, status_code=200)


class VoucherIsValidTests(DiscoveryTestMixin, TestCase):
    def test_valid_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher is valid. """
        voucher, product = prepare_voucher()
        valid, msg, hide_error_message = voucher_is_valid(voucher=voucher, products=[product], request=self.request)

        self.assertTrue(valid)
        self.assertEqual(msg, '')
        self.assertEqual(hide_error_message, None)

    def test_no_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher is invalid. """
        valid, msg, hide_error_message = voucher_is_valid(voucher=None, products=None, request=None)
        self.assertFalse(valid)
        self.assertEqual(msg, 'Coupon does not exist.')
        self.assertFalse(hide_error_message)

    def test_expired_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher has expired. """
        start_datetime = now() - datetime.timedelta(days=20)
        end_datetime = now() - datetime.timedelta(days=10)
        voucher, product = prepare_voucher(start_datetime=start_datetime, end_datetime=end_datetime)
        valid, msg, hide_error_message = voucher_is_valid(voucher=voucher, products=[product], request=None)
        self.assertFalse(valid)
        self.assertEqual(msg, 'This coupon code has expired.')
        self.assertTrue(hide_error_message)

    def test_future_voucher(self):
        """ Verify voucher_is_valid() assess that the voucher has not started yet. """
        start_datetime = now() + datetime.timedelta(days=10)
        end_datetime = now() + datetime.timedelta(days=20)
        voucher, product = prepare_voucher(start_datetime=start_datetime, end_datetime=end_datetime)
        valid, msg, hide_error_message = voucher_is_valid(voucher=voucher, products=[product], request=None)
        self.assertFalse(valid)
        self.assertEqual(msg, 'This coupon code is not yet valid.')
        self.assertFalse(hide_error_message)

    def test_voucher_unavailable_to_buy(self):
        """ Verify that False is returned for unavailable products. """
        voucher, product = prepare_voucher()
        product.expires = pytz.utc.localize(datetime.datetime.min)
        valid, __, hide_error_message = voucher_is_valid(voucher=voucher, products=[product], request=self.request)
        self.assertFalse(valid)
        self.assertFalse(hide_error_message)

    def test_omitting_unavailable_voucher(self):
        """ Verify if there are more than one product, that availability check is omitted. """
        voucher, product = prepare_voucher()
        product.expires = pytz.utc.localize(datetime.datetime.min)
        __, seat = self.create_course_and_seat()
        valid, __, hide_error_message = voucher_is_valid(
            voucher=voucher, products=[product, seat], request=self.request
        )
        self.assertTrue(valid)
        self.assertFalse(hide_error_message)

    def test_once_per_customer_voucher(self):
        """ Verify the coupon is valid for anonymous users. """
        voucher, product = prepare_voucher(usage=Voucher.ONCE_PER_CUSTOMER)
        valid, msg, hide_error_message = voucher_is_valid(voucher=voucher, products=[product], request=self.request)
        self.assertTrue(valid)
        self.assertEqual(msg, '')
        self.assertFalse(hide_error_message)

    def assert_error_messages(self, voucher, product, user, error_msg):
        """ Assert the proper error message is returned. """
        voucher.offers.first().record_usage(discount={'freq': 1, 'discount': 1})
        self.request.user = user
        valid, msg, hide_error_message = voucher_is_valid(voucher=voucher, products=[product], request=self.request)
        self.assertFalse(valid)
        self.assertEqual(msg, error_msg)
        self.assertFalse(hide_error_message)

    def test_usage_exceeded_coupon(self):
        """ Verify voucher_is_valid() assess that the voucher exceeded it's usage limit. """
        voucher, product = prepare_voucher(usage=Voucher.ONCE_PER_CUSTOMER, max_usage=1)
        user = self.create_user()
        error_msg = 'This coupon code is no longer available.'
        self.assert_error_messages(voucher, product, user, error_msg)

    def test_used_voucher(self):
        """Used voucher should not be available."""
        voucher, product = prepare_voucher()
        user = self.create_user()
        order = OrderFactory()

        VoucherApplication.objects.create(voucher=voucher, user=user, order=order)
        error_msg = 'This coupon has already been used'
        self.assert_error_messages(voucher, product, user, error_msg)


@ddt.ddt
class CouponOfferViewTests(ApiMockMixin, CouponMixin, DiscoveryTestMixin, EnterpriseServiceMockMixin,
                           LmsApiMockMixin, TestCase):
    path = reverse('coupons:offer')
    credit_seat = None

    def setUp(self):
        super(CouponOfferViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def test_no_code(self):
        """ Verify a proper response is returned when no code is supplied. """
        response = self.client.get(self.path)
        self.assertEqual(response.context['error'], 'This coupon code is invalid.')

    def test_invalid_voucher(self):
        """ Verify an error is returned when voucher with provided code does not exist. """
        url = format_url(path=self.path, params={'code': 'DOESNTEXIST'})
        response = self.client.get(url)
        self.assertEqual(response.context['error'], 'Coupon does not exist.')

    def test_expired_voucher(self):
        """ Verify proper response is returned for expired vouchers. """
        code = FuzzyText().fuzz().upper()
        start_datetime = now() - datetime.timedelta(days=20)
        end_datetime = now() - datetime.timedelta(days=10)
        prepare_voucher(code=code, start_datetime=start_datetime, end_datetime=end_datetime)

        url = format_url(path=self.path, params={'code': code})
        response = self.client.get(url)
        self.assertEqual(response.context['error'], 'This coupon code has expired.')

    def test_no_product(self):
        """ Verify an error is returned for voucher with no product. """
        code = FuzzyText().fuzz().upper()
        no_product_range = RangeFactory()
        prepare_voucher(code=code, _range=no_product_range)
        url = format_url(path=self.path, params={'code': code})

        response = self.client.get(url)
        self.assertEqual(response.context['error'], 'The voucher is not applicable to your current basket.')

    def prepare_url_for_credit_seat(self, code='CREDIT', enterprise_customer=None):
        """Helper method for creating a credit seat and construct the URL to its offer landing page.

        Returns:
            URL to its offer landing page.
        """
        __, credit_seat = self.create_course_and_seat(seat_type='credit')
        self.credit_seat = credit_seat
        # Make sure to always pair `course_seat_types` and `catalog_query` parameters because
        # if one of them is missing it could result in a SEGFAULT error when running tests
        # with migrations enabled.
        range_kwargs = {
            'products': [credit_seat],
            'course_seat_types': 'credit',
            'catalog_query': '*:*',
            'enterprise_customer': enterprise_customer,
        }
        _range = RangeFactory(**range_kwargs)
        prepare_voucher(code=code, _range=_range)

        return format_url(path=self.path, params={'code': code})

    def test_redirect_to_login(self):
        """User needs be logged in to view the offer page with credit seats."""
        self.client.logout()
        url = self.prepare_url_for_credit_seat()
        response = self.client.get(url)
        expected_url = '{path}?next={next}'.format(path=reverse('login'), next=urllib.parse.quote(url))
        self.assertRedirects(response, expected_url, target_status_code=302)

    def test_credit_seat_response(self):
        """ Verify a logged in user does not get redirected. """
        url = self.prepare_url_for_credit_seat()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_offer_page_context_for_heading(self):
        """
        Verify the response context for logged in user and valid code, contains
        expected heading and heading detail message.
        """
        url = self.prepare_url_for_credit_seat()
        response = self.client.get(url)
        expected_offer_page_heading = 'Welcome to edX'
        expected_offer_page_heading_message = 'Please choose from the courses selected by your ' \
                                              'organization to start learning.'
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['offer_app_page_heading'], expected_offer_page_heading)
        self.assertEqual(response.context['offer_app_page_heading_message'], expected_offer_page_heading_message)

    def test_consent_failed_invalid(self):
        """ Verify that an error is returned if the consent_failed parameter is not a valid SKU. """
        url = '{}&consent_failed={}'.format(self.prepare_url_for_credit_seat(), 'INVALID')
        response = self.client.get(url)
        self.assertEqual(response.context['error'], 'SKU INVALID does not exist.')

    def test_consent_failed_no_enterprise_customer(self):
        """ Verify that an error is returned if the voucher has no associated EnterpriseCustomer. """
        base_url = self.prepare_url_for_credit_seat(enterprise_customer=None)
        sku = self.credit_seat.stockrecords.first().partner_sku
        url = '{}&consent_failed={}'.format(base_url, sku)
        response = self.client.get(url)
        self.assertEqual(
            response.context['error'],
            'There is no Enterprise Customer associated with SKU {sku}.'.format(sku=sku)
        )

    @ddt.data(
        ('', 'If you have concerns about sharing your data, please contact your administrator at BigEnterprise.'),
        (
            'contact@example.com',
            'If you have concerns about sharing your data, please contact your administrator at BigEnterprise at '
            'contact@example.com.',
        ),
    )
    @ddt.unpack
    @httpretty.activate
    def test_consent_failed_message(self, contact_email, expected_response):
        """ Verify that the consent failure message shows up when the consent_failed parameter is a valid SKU. """
        self.mock_access_token_response()
        self.mock_specific_enterprise_customer_api(
            ENTERPRISE_CUSTOMER,
            contact_email=contact_email
        )
        base_url = self.prepare_url_for_credit_seat(enterprise_customer=ENTERPRISE_CUSTOMER)
        sku = self.credit_seat.stockrecords.first().partner_sku
        url = '{}&consent_failed={}'.format(base_url, sku)
        response = self.client.get(url)
        self.assertContains(
            response,
            'Enrollment in {course_name} was not complete.'.format(course_name=self.credit_seat.course.name),
            status_code=200
        )
        self.assertContains(response, expected_response, status_code=200)


@ddt.ddt
class CouponRedeemViewTests(CouponMixin, DiscoveryTestMixin, LmsApiMockMixin, EnterpriseServiceMockMixin,
                            TestCase, DiscoveryMockMixin):
    redeem_url = reverse('coupons:redeem')

    def setUp(self):
        super(CouponRedeemViewTests, self).setUp()
        self.user = self.create_user(email='test@tester.fake')
        self.client.login(username=self.user.username, password=self.password)
        self.course_mode = 'verified'
        self.course, self.seat = self.create_course_and_seat(
            seat_type=self.course_mode,
            id_verification=True,
            price=50,
            partner=self.partner
        )
        self.stock_record = StockRecord.objects.get(product=self.seat)
        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(StockRecord.objects.get(product=self.seat))

    def redeem_url_with_params(self, code=COUPON_CODE, consent_token=None):
        """ Constructs the coupon redemption URL with the proper string query parameters. """
        params = {
            'code': code,
            'sku': self.stock_record.partner_sku,
        }
        if consent_token is not None:
            params['consent_token'] = consent_token
        return format_url(base=self.redeem_url, params=params)

    def create_coupon_and_get_code(
            self,
            benefit_value=90,
            code=COUPON_CODE,
            email_domains=None,
            enterprise_customer=None,
            enterprise_customer_catalog=None,
            course_id=None,
            catalog=None,
            contract_discount_value=None,
            contract_discount_type=EnterpriseContractMetadata.PERCENTAGE,
            prepaid_invoice_amount=None,
    ):
        """ Creates coupon and returns code. """
        coupon = self.create_coupon(
            benefit_value=benefit_value,
            catalog=catalog,
            code=code,
            email_domains=email_domains,
            enterprise_customer=enterprise_customer,
            enterprise_customer_catalog=enterprise_customer_catalog,
        )
        coupon.course_id = course_id
        if contract_discount_value is not None:
            ecm = EnterpriseContractMetadata.objects.create(
                discount_type=contract_discount_type,
                discount_value=contract_discount_value,
                amount_paid=prepaid_invoice_amount,
            )
            coupon.attr.enterprise_contract_metadata = ecm
        coupon.save()
        coupon_code = coupon.attr.coupon_vouchers.vouchers.first().code
        self.assertEqual(Voucher.objects.filter(code=coupon_code).count(), 1)
        return coupon_code, coupon

    def redeem_coupon(self, code=COUPON_CODE, consent_token=None):
        self.request.user = self.user
        return self.client.get(self.redeem_url_with_params(code=code, consent_token=consent_token))

    def assert_redirects_to_receipt_page(self, code=COUPON_CODE, consent_token=None):
        response = self.redeem_coupon(code=code, consent_token=consent_token)

        order = Order.objects.first()
        receipt_page_url = get_receipt_page_url(self.site.siteconfiguration)
        expected_url = format_url(
            base=receipt_page_url,
            params={
                'order_number': order.number,
                'disable_back_button': 1,
            },
        )

        self.assertRedirects(response, expected_url, status_code=302, fetch_redirect_response=False)

    def assert_redemption_page_redirects(self, expected_url, target=200, code=COUPON_CODE, consent_token=None):
        """ Verify redirect from redeem page to expected page. """
        response = self.redeem_coupon(code=code, consent_token=consent_token)
        self.assertRedirects(
            response, expected_url, status_code=302, target_status_code=target, fetch_redirect_response=False
        )

    def test_login_required(self):
        """ Users are required to login before accessing the view. """
        self.client.logout()
        response = self.client.get(self.redeem_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.url)

    def test_code_not_provided(self):
        """ Verify a response message is returned when no code is provided. """
        url_without_code = format_url(base=self.redeem_url, params={'sku': self.stock_record.partner_sku})
        response = self.client.get(url_without_code)
        self.assertEqual(response.context['error'], 'Code not provided.')

    def test_sku_not_provided(self):
        """ Verify a response message is returned when no SKU is provided. """
        url_without_sku = format_url(base=self.redeem_url, params={'code': COUPON_CODE})
        response = self.client.get(url_without_sku)
        self.assertEqual(response.context['error'], 'SKU not provided.')

    def test_invalid_voucher_code(self):
        """ Verify an error is returned when voucher does not exist. """
        code = FuzzyText().fuzz().upper()
        url = format_url(base=self.redeem_url, params={'code': code, 'sku': self.stock_record.partner_sku})
        response = self.client.get(url)
        msg = 'No voucher found with code {code}'.format(code=code)
        self.assertEqual(response.context['error'], msg)

    def test_no_product(self):
        """ Verify an error is returned when a stock record for the provided SKU doesn't exist. """
        self.create_coupon_and_get_code(catalog=self.catalog)
        url = format_url(base=self.redeem_url, params={'code': COUPON_CODE, 'sku': 'INVALID'})
        response = self.client.get(url)
        self.assertEqual(response.context['error'], 'The product does not exist.')

    def test_expired_voucher(self):
        """ Verify an error is returned for expired coupon. """
        start_datetime = now() - datetime.timedelta(days=20)
        end_datetime = now() - datetime.timedelta(days=10)
        code = FuzzyText().fuzz().upper()
        __, product = prepare_voucher(code=code, start_datetime=start_datetime, end_datetime=end_datetime)

        url = format_url(base=self.redeem_url, params={
            'code': code,
            'sku': StockRecord.objects.get(product=product).partner_sku
        })
        response = self.client.get(url)
        self.assertEqual(response.context['error'], 'This coupon code has expired.')

    @httpretty.activate
    def test_invalid_entitlement_course(self):
        """ Verify an error is returned when you apply enterprise coupon on entitled product. """
        entitle_product = ProductFactory(
            product_class=self.entitlement_product_class, stockrecords__partner=self.partner,
            stockrecords__price_currency='USD', categories=[]
        )
        self.catalog.stock_records.add(StockRecord.objects.get(product=entitle_product))
        code, _ = self.prepare_enterprise_data(catalog=self.catalog)

        response = self.client.get(
            format_url(
                base=self.redeem_url, params={
                    'code': code,
                    'sku': StockRecord.objects.get(product=entitle_product).partner_sku
                }
            )
        )
        self.assertEqual(
            response.context['error'],
            'This coupon is not valid for purchasing a program. Try using this on an individual course in the program. '
            'If you need assistance, contact edX support.'
        )

    @httpretty.activate
    def test_basket_redirect_discount_code(self):
        """ Verify the view redirects to the basket view when a discount code is provided. """
        self.mock_course_api_response(course=self.course)
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        self.mock_access_token_response()

        self.create_coupon(catalog=self.catalog, code=COUPON_CODE, benefit_value=5)
        self.assert_redemption_page_redirects(self.get_coupon_redeem_success_expected_redirect_url())

    @httpretty.activate
    def test_basket_redirect_enrollment_code(self):
        """ Verify the view redirects to the receipt page when an enrollment code is provided. """
        code, _ = self.create_coupon_and_get_code(benefit_value=100, code='', catalog=self.catalog)
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        self.mock_access_token_response()

        self.assert_redirects_to_receipt_page(code=code)

    @httpretty.activate
    @mock.patch.object(EdxOrderPlacementMixin, 'place_free_order')
    def test_basket_redirect_enrollment_code_error(self, place_free_order):
        """ Verify the view redirects to checkout error page when an order hasn't completed. """
        code, _ = self.create_coupon_and_get_code(benefit_value=100, code='', catalog=self.catalog)
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        self.mock_access_token_response()
        place_free_order.return_value = Exception

        with mock.patch('ecommerce.coupons.views.logger.exception') as mock_logger:
            self.assert_redemption_page_redirects(
                self.get_full_url(reverse('checkout:error')),
                target=301,
                code=code
            )
            self.assertTrue(mock_logger.called)

    def prepare_enterprise_data(self, benefit_value=100, consent_enabled=True, consent_provided=False, course_id=None,
                                catalog=None, enterprise_customer_catalog=None, contract_discount_value=None,
                                contract_discount_type=EnterpriseContractMetadata.PERCENTAGE,
                                prepaid_invoice_amount=None):
        """Creates an enterprise coupon and mocks enterprise endpoints."""
        code, coupon = self.create_coupon_and_get_code(
            benefit_value=benefit_value,
            code='',
            enterprise_customer=ENTERPRISE_CUSTOMER,
            course_id=course_id,
            catalog=catalog,
            enterprise_customer_catalog=enterprise_customer_catalog,
            contract_discount_type=contract_discount_type,
            contract_discount_value=contract_discount_value,
            prepaid_invoice_amount=prepaid_invoice_amount,
        )
        self.request.user = self.user
        self.mock_consent_response(
            self.user.username,
            course_id,
            ENTERPRISE_CUSTOMER,
            granted=consent_provided,
            required=(consent_enabled and not consent_provided),
            exists=(not consent_provided),
        )
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        self.mock_access_token_response()
        self.mock_specific_enterprise_customer_api(uuid=ENTERPRISE_CUSTOMER, consent_enabled=consent_enabled)
        return code, coupon

    @httpretty.activate
    def test_enterprise_customer_redirect_no_consent(self):
        """ Verify the view redirects to LMS when an enrollment code is provided. """
        code, _ = self.prepare_enterprise_data(catalog=self.catalog)
        consent_token = get_enterprise_customer_data_sharing_consent_token(
            self.request.user.access_token,
            self.course.id,
            ENTERPRISE_CUSTOMER
        )
        expected_url = get_enterprise_course_consent_url(
            self.site,
            code,
            self.stock_record.partner_sku,
            consent_token,
            self.course.id,
            ENTERPRISE_CUSTOMER
        )

        response = self.client.get(self.redeem_url_with_params(code=code))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)

    @httpretty.activate
    def test_enterprise_customer_invalid_consent_token(self):
        """ Verify that the view renders an error when the consent token doesn't match. """
        code, _ = self.prepare_enterprise_data(catalog=self.catalog)
        self.request.user = self.user
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        self.mock_access_token_response()
        self.mock_specific_enterprise_customer_api(ENTERPRISE_CUSTOMER)
        self.mock_enterprise_learner_api(consent_provided=False)
        self.mock_enterprise_course_enrollment_api(results_present=False)

        response = self.client.get(self.redeem_url_with_params(code=code, consent_token='invalid_consent_token'))
        self.assertEqual(response.context['error'], 'Invalid data sharing consent token provided.')

    @httpretty.activate
    def test_enterprise_customer_does_not_exist(self):
        """
        Verify that a generic error is rendered when the corresponding EnterpriseCustomer doesn't exist
        on the Enterprise service.
        """
        code, _ = self.prepare_enterprise_data(catalog=self.catalog)
        self.mock_enterprise_customer_api_not_found(ENTERPRISE_CUSTOMER)
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        response = self.client.get(self.redeem_url_with_params(code=code))
        self.assertEqual(response.context['error'], 'Couldn\'t find a matching Enterprise Customer for this coupon.')

    @httpretty.activate
    def test_enterprise_contract_metadata_create_on_coupon_redemption(self):
        """
        Verify an orderline is updated with calculated enterprise discount data
        if a product is fulfilled with a coupon for an enterprise customer and
        that coupon has `enterprise_contract_metadata` associated with it.
        """
        code, _ = self.prepare_enterprise_data(
            enterprise_customer_catalog=ENTERPRISE_CUSTOMER_CATALOG,
            contract_discount_type=EnterpriseContractMetadata.FIXED,
            contract_discount_value=Decimal('1337.00'),
            prepaid_invoice_amount=Decimal('2000.00'),
        )
        self.mock_assignable_enterprise_condition_calls(ENTERPRISE_CUSTOMER_CATALOG)
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        self.mock_enterprise_learner_post_api()

        consent_token = get_enterprise_customer_data_sharing_consent_token(
            self.request.user.access_token,
            self.course.id,
            ENTERPRISE_CUSTOMER
        )

        self.request.user = self.user
        self.client.get(self.redeem_url_with_params(code=code, consent_token=consent_token))

        # Assert our orderline has attributes updated with some decimal value
        orderline = Order.objects.first().lines.last()
        self.assertIsInstance(orderline.effective_contract_discount_percentage, Decimal)
        self.assertIsInstance(orderline.effective_contract_discounted_price, Decimal)

    @httpretty.activate
    def test_enterprise_contract_metadata_not_created(self):
        """
        Verify an orderline is NOT updated with calculated enterprise discount data
        if a product is fulfilled with a coupon for an enterprise customer but
        that coupon has NO `enterprise_contract_metadata` associated with it.
        """
        code, _ = self.prepare_enterprise_data(
            enterprise_customer_catalog=ENTERPRISE_CUSTOMER_CATALOG,
        )
        self.mock_assignable_enterprise_condition_calls(ENTERPRISE_CUSTOMER_CATALOG)
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        self.mock_enterprise_learner_post_api()

        consent_token = get_enterprise_customer_data_sharing_consent_token(
            self.request.user.access_token,
            self.course.id,
            ENTERPRISE_CUSTOMER
        )

        self.request.user = self.user
        self.client.get(self.redeem_url_with_params(code=code, consent_token=consent_token))

        # Assert our orderline has nothing set for enterprise discount fields
        orderline = Order.objects.first().lines.last()
        assert orderline.effective_contract_discount_percentage is None
        assert orderline.effective_contract_discounted_price is None

    @httpretty.activate
    def test_enterprise_customer_successful_redemption(self):
        """ Verify the view redirects to LMS when valid consent is provided. """
        code, _ = self.prepare_enterprise_data(enterprise_customer_catalog=ENTERPRISE_CUSTOMER_CATALOG)
        self.mock_assignable_enterprise_condition_calls(ENTERPRISE_CUSTOMER_CATALOG)
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        self.mock_enterprise_learner_post_api()

        consent_token = get_enterprise_customer_data_sharing_consent_token(
            self.request.user.access_token,
            self.course.id,
            ENTERPRISE_CUSTOMER
        )

        self.assert_redirects_to_receipt_page(
            code=code,
            consent_token=consent_token
        )
        last_request = httpretty.last_request()
        self.assertEqual(last_request.path, '/api/enrollment/v1/enrollment')
        self.assertEqual(last_request.method, 'POST')

    @httpretty.activate
    def test_enterprise_customer_successful_redemption_message(self):
        """ Verify the info message appears on successful redemption. """
        expected_message = 'A discount has been applied, courtesy of BigEnterprise.'

        # Setting benefit value to a low amount to ensure the basket is not free,
        # and calls to the checkout page do not redirect away from the checkout page.
        code, _ = self.prepare_enterprise_data(
            benefit_value=5, consent_enabled=False, catalog=self.catalog,
            enterprise_customer_catalog=ENTERPRISE_CUSTOMER_CATALOG
        )
        self.mock_assignable_enterprise_condition_calls(ENTERPRISE_CUSTOMER_CATALOG)

        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        self.mock_enterprise_learner_post_api()

        response = self.client.get(self.redeem_url_with_params(code=code), follow=True)
        messages = []
        messages += response.context['messages']
        self.assertEqual(messages[0].tags, 'info')
        self.assertEqual(messages[0].message, expected_message)

    @httpretty.activate
    def test_enterprise_customer_coupon_redemption_for_invalid_course(self):
        """ Verify the warning message appears on redemption if coupon does not belong to course. """
        expected_message = 'This coupon code is not valid for this course. Try a different course.'

        course, seat = self.create_course_and_seat()
        stock_record = StockRecord.objects.get(product=seat)

        # Setting benefit value to a low amount to ensure the basket is not free,
        # and calls to the checkout page do not redirect away from the checkout page.
        code, _ = self.prepare_enterprise_data(benefit_value=5, consent_enabled=False, course_id=course.id)

        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        self.mock_enterprise_learner_post_api()
        self.mock_course_run_detail_endpoint(course, discovery_api_url=self.site_configuration.discovery_api_url)
        params = {
            'code': code,
            'sku': stock_record.partner_sku,
        }
        response = self.client.get(
            format_url(base=self.redeem_url, params=params),
            follow=True,
        )
        messages = []
        messages += response.context['messages']
        self.assertEqual(messages[0].tags, 'warning')
        self.assertEqual(messages[0].message, expected_message)

    @httpretty.activate
    def test_enterprise_customer_coupon_redemption_for_no_offer_assignment(self):
        """
        Verify the warning message appears on redemption if coupon does not have any
        offer assignments for the user.
        """
        expected_message = (
            'This code is not valid with your email. '
            'Please login with the correct email assigned '
            'to the code or contact your Learning Manager '
            'for additional questions.'
        )

        code, coupon = self.prepare_enterprise_data(
            benefit_value=5, consent_enabled=False, catalog=self.catalog,
            enterprise_customer_catalog=ENTERPRISE_CUSTOMER_CATALOG
        )
        self.mock_assignable_enterprise_condition_calls(ENTERPRISE_CUSTOMER_CATALOG)
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()
        self.mock_enterprise_learner_post_api()
        self.mock_course_run_detail_endpoint(self.course, discovery_api_url=self.site_configuration.discovery_api_url)

        data = {'codes': [code], 'emails': ['foo@bar.org']}
        serializer = CouponCodeAssignmentSerializer(data=data, context={'coupon': coupon})
        if serializer.is_valid():
            serializer.save()

        response = self.client.get(self.redeem_url_with_params(code=code), follow=True)

        messages = []
        messages += response.context['messages']
        self.assertEqual(messages[0].tags, 'warning')
        self.assertEqual(messages[0].message, expected_message)

    @httpretty.activate
    def test_multiple_vouchers(self):
        """ Verify a redirect to LMS happens when a basket with already existing vouchers is used. """
        code, _ = self.create_coupon_and_get_code(benefit_value=100, code='', catalog=self.catalog)
        basket = Basket.get_basket(self.user, self.site)
        basket.vouchers.add(Voucher.objects.get(code=code))

        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        self.mock_access_token_response()

        self.assert_redirects_to_receipt_page(code=code)

    @httpretty.activate
    def test_already_enrolled_rejection(self):
        """ Verify a user is rejected from redeeming a coupon for a course he's already enrolled in."""
        self.mock_account_api(self.request, self.user.username, data={'is_active': True})
        self.mock_access_token_response()
        self.create_coupon_and_get_code(catalog=self.catalog)
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=True):
            response = self.client.get(self.redeem_url_with_params())
            msg = 'You have already purchased {course} seat.'.format(course=self.course.name)
            self.assertEqual(response.context['error'], msg)

    @httpretty.activate
    def test_invalid_email_domain_rejection(self):
        """ Verify a user with invalid email domain is rejected. """
        self.create_coupon_and_get_code(email_domains='example.com', catalog=self.catalog)
        response = self.client.get(self.redeem_url_with_params())
        msg = 'You are not eligible to use this coupon.'
        self.assertEqual(response.context['error'], msg)

    def assert_redirected_to_email_confirmation(self, response):
        expected_redirect_url = '/offers/email_confirmation/?{}'.format(
            urllib.parse.urlencode({'course_id': self.course.id})
        )
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertIn(expected_redirect_url, response.url)

    @httpretty.activate
    def test_inactive_user_rejection(self):
        """ Verify that a user who hasn't activated the account is rejected. """
        self.mock_account_api(self.request, self.user.username, data={'is_active': False})
        self.create_coupon_and_get_code(catalog=self.catalog)
        self.mock_access_token_response()

        response = self.client.get(self.redeem_url_with_params())
        self.assert_redirected_to_email_confirmation(response)

    @httpretty.activate
    def test_inactive_user_requirement_disabled(self):
        """
        Verify that a user who hasn't activated their account is redirected to the basket view
        when the account activation requirement has been disabled.
        """
        self.site.siteconfiguration.require_account_activation = False
        self.site.siteconfiguration.save()
        self.mock_account_api(self.request, self.user.username, data={'is_active': False})
        self.mock_access_token_response()

        self.create_coupon(catalog=self.catalog, code=COUPON_CODE, benefit_value=5)
        self.assert_redemption_page_redirects(self.get_coupon_redeem_success_expected_redirect_url())

    @httpretty.activate
    def test_inactive_user_email_domain_restricted_coupon_redemption(self):
        """
        Verify that a user must activate their account before being allowed
        to redeem an email domain-restricted coupon.
        """
        self.mock_account_api(self.request, self.user.username, data={'is_active': False})
        self.mock_access_token_response()
        email_domain = self.user.email.split('@')[1]
        self.create_coupon(catalog=self.catalog, code=COUPON_CODE, benefit_value=5, email_domains=email_domain)

        response = self.client.get(self.redeem_url_with_params())
        self.assert_redirected_to_email_confirmation(response)

    def get_coupon_redeem_success_expected_redirect_url(self):
        return self.get_full_url(path=reverse('basket:summary')) + '?coupon_redeem_redirect=1'


@ddt.ddt
class EnrollmentCodeCsvViewTests(TestCase):
    """ Tests for the EnrollmentCodeCsvView view. """
    path = 'coupons:enrollment_code_csv'

    def setUp(self):
        super(EnrollmentCodeCsvViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def test_invalid_order_number(self):
        """ Verify a 404 error is raised for an invalid order number. """
        response = self.client.get(reverse(self.path, args=['INVALID']))
        self.assertEqual(response.status_code, 404)

    def test_invalid_user(self):
        """ Verify an unauthorized request is redirected to the LMS dashboard. """
        order = OrderFactory()
        order.user = self.create_user()
        response = self.client.get(reverse(self.path, args=[order.number]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['location'], get_lms_url('dashboard'))

    @ddt.data(
        u'Plain English product title',
        u'Unicode product títle 可以用“我不太懂艺术 但我知道我喜欢什么”做比喻'
    )
    def test_successful_response(self, product_title):
        """ Verify a successful response is returned. """
        voucher = VoucherFactory()
        order = OrderFactory(user=self.user)
        product = ProductFactory(title=product_title, categories=[])
        line = OrderLineFactory(order=order, product=product, partner_sku='test_sku')
        order_line_vouchers = OrderLineVouchers.objects.create(line=line)
        order_line_vouchers.vouchers.add(voucher)

        response = self.client.get(reverse(self.path, args=[order.number]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['content-type'], 'text/csv')
