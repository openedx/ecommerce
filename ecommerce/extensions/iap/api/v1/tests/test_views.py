import datetime
import json
import urllib.error
import urllib.parse

import app_store_notifications_v2_validator as asn2
import ddt
import mock
import pytz
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from oauth2client.service_account import ServiceAccountCredentials
from oscar.apps.order.exceptions import UnableToPlaceOrder
from oscar.apps.payment.exceptions import GatewayError, PaymentError
from oscar.core.loading import get_class, get_model
from oscar.test.factories import BasketFactory
from rest_framework import status
from testfixtures import LogCapture

from ecommerce.core.tests import toggle_switch
from ecommerce.coupons.tests.mixins import DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.api.tests.test_authentication import AccessTokenMixin
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE
from ecommerce.extensions.basket.tests.mixins import BasketMixin
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.iap.api.v1.constants import (
    COURSE_ALREADY_PAID_ON_DEVICE,
    ERROR_ALREADY_PURCHASED,
    ERROR_BASKET_ID_NOT_PROVIDED,
    ERROR_BASKET_NOT_FOUND,
    ERROR_DURING_ORDER_CREATION,
    ERROR_DURING_PAYMENT_HANDLING,
    ERROR_DURING_POST_ORDER_OP,
    ERROR_ORDER_NOT_FOUND_FOR_REFUND,
    ERROR_REFUND_NOT_COMPLETED,
    ERROR_TRANSACTION_NOT_FOUND_FOR_REFUND,
    IGNORE_NON_REFUND_NOTIFICATION_FROM_APPLE,
    LOGGER_BASKET_ALREADY_PURCHASED,
    LOGGER_BASKET_CREATED,
    LOGGER_BASKET_CREATION_FAILED,
    LOGGER_BASKET_NOT_FOUND,
    LOGGER_EXECUTE_ALREADY_PURCHASED,
    LOGGER_EXECUTE_GATEWAY_ERROR,
    LOGGER_EXECUTE_ORDER_CREATION_FAILED,
    LOGGER_EXECUTE_PAYMENT_ERROR,
    LOGGER_EXECUTE_REDUNDANT_PAYMENT,
    LOGGER_EXECUTE_STARTED,
    LOGGER_EXECUTE_SUCCESSFUL,
    LOGGER_PAYMENT_FAILED_FOR_BASKET,
    LOGGER_REFUND_SUCCESSFUL,
    LOGGER_STARTING_PAYMENT_FLOW,
    NO_PRODUCT_AVAILABLE,
    PRODUCTS_DO_NOT_EXIST,
    RECEIVED_NOTIFICATION_FROM_APPLE
)
from ecommerce.extensions.iap.api.v1.google_validator import GooglePlayValidator
from ecommerce.extensions.iap.api.v1.ios_validator import IOSValidator
from ecommerce.extensions.iap.api.v1.serializers import MobileOrderSerializer
from ecommerce.extensions.iap.api.v1.views import AndroidRefundView, MobileCoursePurchaseExecutionView
from ecommerce.extensions.iap.processors.android_iap import AndroidIAP
from ecommerce.extensions.iap.processors.ios_iap import IOSIAP
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder
from ecommerce.extensions.payment.exceptions import RedundantPaymentNotificationError
from ecommerce.extensions.payment.models import PaymentProcessorResponse
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin
from ecommerce.extensions.refund.status import REFUND, REFUND_LINE
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.extensions.test.factories import create_basket, create_order
from ecommerce.tests.factories import ProductFactory, StockRecordFactory
from ecommerce.tests.mixins import JwtMixin, LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Catalog = get_model('catalogue', 'Catalog')
Product = get_model('catalogue', 'Product')
Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
Option = get_model('catalogue', 'Option')
Refund = get_model('refund', 'Refund')
post_refund = get_class('refund.signals', 'post_refund')


@ddt.ddt
class MobileBasketAddItemsViewTests(DiscoveryMockMixin, LmsApiMockMixin, BasketMixin,
                                    EnterpriseServiceMockMixin, TestCase):
    """ MobileBasketAddItemsView view tests. """
    path = reverse('iap:mobile-basket-add')
    logger_name = 'ecommerce.extensions.iap.api.v1.views'

    def setUp(self):
        super(MobileBasketAddItemsViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory(partner=self.partner)
        product = self.course.create_or_update_seat('verified', False, 50)
        self.stock_record = StockRecordFactory(product=product, partner=self.partner)
        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(self.stock_record)

    def _get_response(self, product_skus, **url_params):
        qs = urllib.parse.urlencode({'sku': product_skus}, True)
        url = '{root}?{qs}'.format(root=self.path, qs=qs)
        for name, value in url_params.items():
            url += '&{}={}'.format(name, value)
        return self.client.get(url)

    def test_add_multiple_products_to_basket(self):
        """ Verify the basket accepts multiple products. """
        with LogCapture(self.logger_name) as logger:
            products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
            skus = [product.stockrecords.first().partner_sku for product in products]
            response = self._get_response(skus)
            self.assertEqual(response.status_code, 200)
            logger.check((self.logger_name, 'INFO', LOGGER_STARTING_PAYMENT_FLOW % (self.user.username, skus)),
                         (self.logger_name, 'INFO', LOGGER_BASKET_CREATED % (self.user.username, skus)))

        request = response.wsgi_request
        basket = Basket.get_basket(request.user, request.site)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), len(products))

    def test_add_multiple_products_no_skus_provided(self):
        """ Verify the Bad request exception is thrown when no skus are provided. """
        with LogCapture(self.logger_name) as logger:
            error = 'No SKUs provided.'
            response = self.client.get(self.path)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()['error'], error)
            logger.check((self.logger_name, 'ERROR', LOGGER_BASKET_CREATION_FAILED % (self.user.username, error)))

    def test_add_multiple_products_no_available_products(self):
        """
        Verify that adding multiple products to the basket results in an error if
        the products do not exist.
        """
        response = self.client.get(self.path, data=[('sku', 1), ('sku', 2)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], PRODUCTS_DO_NOT_EXIST.format(skus='1, 2'))

    def test_all_already_purchased_products(self):
        """
        Test user can not purchase products again using the multiple item view
        """
        course = CourseFactory(partner=self.partner)
        product1 = course.create_or_update_seat("Verified", True, 0)
        product2 = course.create_or_update_seat("Professional", True, 0)
        stock_record = StockRecordFactory(product=product1, partner=self.partner)
        catalog = Catalog.objects.create(partner=self.partner)
        catalog.stock_records.add(stock_record)
        stock_record = StockRecordFactory(product=product2, partner=self.partner)
        catalog.stock_records.add(stock_record)

        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=True), \
                LogCapture(self.logger_name) as logger:
            response = self._get_response(
                [product.stockrecords.first().partner_sku for product in [product1, product2]],
            )
            self.assertEqual(response.status_code, 406)
            self.assertEqual(response.json()['error'], ERROR_ALREADY_PURCHASED)
            expected_skus = [product.stockrecords.first().partner_sku for product in [product1, product2]]
            logger.check(
                (
                    self.logger_name,
                    'INFO',
                    LOGGER_STARTING_PAYMENT_FLOW % (self.user.username, expected_skus)
                ),
                (
                    self.logger_name,
                    'ERROR',
                    LOGGER_BASKET_ALREADY_PURCHASED % (self.user.username, expected_skus)
                ),
            )

    def test_not_already_purchased_products(self):
        """
        Test user can purchase products which have not been already purchased
        """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=False):
            response = self._get_response([product.stockrecords.first().partner_sku for product in products])
            self.assertEqual(response.status_code, 200)

    def test_one_already_purchased_product(self):
        """
        Test prepare_basket removes already purchased product and checkout for the rest of products
        """
        order = create_order(site=self.site, user=self.user)
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        products.append(OrderLine.objects.get(order=order).product)
        response = self._get_response([product.stockrecords.first().partner_sku for product in products])
        request = response.wsgi_request
        basket = Basket.get_basket(request.user, request.site)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(basket.lines.count(), len(products) - 1)

    def test_no_available_product(self):
        """ The view should return HTTP 400 if the product is not available for purchase. """
        product = self.stock_record.product
        product.expires = pytz.utc.localize(datetime.datetime.min)
        product.save()
        self.assertFalse(Selector().strategy().fetch_for_product(product).availability.is_available_to_buy)

        expected_content = NO_PRODUCT_AVAILABLE
        response = self._get_response(self.stock_record.partner_sku)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], expected_content)

    def test_with_both_unavailable_and_available_products(self):
        """ Verify the basket ignores unavailable products and continue with available products. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)

        products[0].expires = pytz.utc.localize(datetime.datetime.min)
        products[0].save()
        self.assertFalse(Selector().strategy().fetch_for_product(products[0]).availability.is_available_to_buy)

        response = self._get_response([product.stockrecords.first().partner_sku for product in products])
        self.assertEqual(response.status_code, 200)

        request = response.wsgi_request
        basket = Basket.get_basket(request.user, request.site)
        self.assertEqual(basket.status, Basket.OPEN)

    @ddt.data(
        ('false', 'False'),
        ('true', 'True'),
    )
    @ddt.unpack
    def test_email_opt_in_when_explicitly_given(self, opt_in, expected_value):
        """
        Verify the email_opt_in query string is saved into a BasketAttribute.
        """
        response = self._get_response(self.stock_record.partner_sku, email_opt_in=opt_in)
        request = response.wsgi_request
        basket = Basket.get_basket(request.user, request.site)
        basket_attribute = BasketAttribute.objects.get(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
        )
        self.assertEqual(basket_attribute.value_text, expected_value)

    def test_email_opt_in_when_not_given(self):
        """
        Verify that email_opt_in defaults to false if not specified.
        """
        response = self._get_response(self.stock_record.partner_sku)
        request = response.wsgi_request
        basket = Basket.get_basket(request.user, request.site)
        basket_attribute = BasketAttribute.objects.get(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
        )
        self.assertEqual(basket_attribute.value_text, 'False')


class MobileCoursePurchaseExecutionViewTests(PaymentEventsMixin, TestCase):
    """ MobileCoursePurchaseExecutionView view tests. """
    path = reverse('iap:iap-execute')

    def setUp(self):
        super(MobileCoursePurchaseExecutionViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory(partner=self.partner)
        product = self.course.create_or_update_seat('verified', False, 50)
        self.basket = create_basket(
            owner=self.user, site=self.site, price='50.0', product_class=product.product_class
        )
        self.basket.freeze()

        self.processor = AndroidIAP(self.site)
        self.processor_name = self.processor.NAME
        self.logger_name = 'ecommerce.extensions.iap.api.v1.views'

        self.post_data = {
            'transactionId': 'transactionId.android.test.purchased',
            'productId': 'android.test.purchased',
            'purchaseToken': 'inapp:org.edx.mobile:android.test.purchased',
            'payment_processor': 'android-iap',
            'basket_id': self.basket.id
        }
        order_message = "Order Failure: {} payment was received, but an order for basket [{}] could not be placed."
        self.order_placement_error_message = order_message.format(self.processor.NAME.title(), self.basket.id)

    def _assert_response(self, error_message):
        """
        Check if response is as expected.
        """
        response = self.client.post(self.path, data=self.post_data)
        self.assertEqual(response.json(), error_message)
        return response

    def test_payment_error(self):
        """
        Verify that a user who has approved payment is redirected to the configured receipt
        page when payment execution fails.
        """
        with mock.patch.object(MobileCoursePurchaseExecutionView, 'handle_payment',
                               side_effect=PaymentError('Test Error')) as fake_handle_payment:
            with LogCapture(self.logger_name) as logger:
                self._assert_response({'error': ERROR_DURING_PAYMENT_HANDLING})
                self.assertTrue(fake_handle_payment.called)

                logger.check(
                    (
                        self.logger_name,
                        'INFO',
                        LOGGER_EXECUTE_STARTED % (self.user.username, self.basket.id, self.processor_name)
                    ),
                    (
                        self.logger_name,
                        'ERROR',
                        LOGGER_EXECUTE_PAYMENT_ERROR % (self.user.username, self.basket.id,
                                                        str(fake_handle_payment.side_effect))
                    ),
                )

    def test_gateway_error(self):
        """
        Verify that an error is thrown when an approved payment fails to execute
        """
        with mock.patch.object(MobileCoursePurchaseExecutionView, 'handle_payment',
                               side_effect=GatewayError('Test Error')) as fake_handle_payment:
            with LogCapture(self.logger_name) as logger:
                self._assert_response({'error': ERROR_DURING_PAYMENT_HANDLING})
                self.assertTrue(fake_handle_payment.called)

                logger.check(
                    (
                        self.logger_name,
                        'INFO',
                        LOGGER_EXECUTE_STARTED % (self.user.username, self.basket.id, self.processor_name)
                    ),
                    (
                        self.logger_name,
                        'ERROR',
                        LOGGER_EXECUTE_GATEWAY_ERROR % (self.user.username, self.basket.id,
                                                        str(fake_handle_payment.side_effect))
                    ),
                )

    def test_unanticipated_error_during_payment_handling(self):
        """
        Verify that a user who has approved payment is redirected to the configured receipt
        page when payment execution fails in an unanticipated manner.
        """
        with mock.patch.object(MobileCoursePurchaseExecutionView, 'handle_payment',
                               side_effect=KeyError('Test Error')) as fake_handle_payment:
            with LogCapture(self.logger_name) as logger:
                self._assert_response({'error': ERROR_DURING_PAYMENT_HANDLING})
                self.assertTrue(fake_handle_payment.called)

                logger.check_present(
                    (
                        self.logger_name,
                        'ERROR',
                        LOGGER_PAYMENT_FAILED_FOR_BASKET % (self.basket.id, str(fake_handle_payment.side_effect))
                    ),
                )

    def test_unable_to_place_order(self):
        """
        Verify that a user who has approved payment is redirected to the configured receipt
        page when the payment is executed but an order cannot be placed.
        """
        with mock.patch.object(MobileCoursePurchaseExecutionView, 'handle_order_placement',
                               side_effect=UnableToPlaceOrder('Test Error')) as fake_handle_order_placement, \
                mock.patch.object(GooglePlayValidator, 'validate') as fake_google_validation, \
                LogCapture(self.DUPLICATE_ORDER_LOGGER_NAME) as logger_one, \
                LogCapture(self.logger_name) as logger_two:
            fake_google_validation.return_value = {
                'resource': {
                    'orderId': 'orderId.android.test.purchased'
                }
            }
            self._assert_response({'error': ERROR_DURING_ORDER_CREATION})
            self.assertTrue(fake_google_validation.called)
            self.assertTrue(fake_handle_order_placement.called)
            logger_one.check(
                (self.DUPLICATE_ORDER_LOGGER_NAME, 'ERROR', self.order_placement_error_message),
            )
            logger_two.check(
                (
                    self.logger_name,
                    'INFO',
                    LOGGER_EXECUTE_STARTED % (self.user.username, self.basket.id, self.processor_name)
                ),
                (
                    self.logger_name,
                    'ERROR',
                    LOGGER_EXECUTE_ORDER_CREATION_FAILED % (self.user.username, self.basket.id,
                                                            str(fake_handle_order_placement.side_effect))
                ))

    def test_unanticipated_error_during_order_placement(self):
        """
        Verify that unanticipated errors during order placement are handled gracefully.
        """
        with mock.patch.object(MobileCoursePurchaseExecutionView, 'handle_order_placement',
                               side_effect=UnableToPlaceOrder) as fake_handle_order_placement, \
                mock.patch.object(GooglePlayValidator, 'validate') as fake_google_validation, \
                LogCapture(self.DUPLICATE_ORDER_LOGGER_NAME) as logger:
            fake_google_validation.return_value = {
                'resource': {
                    'orderId': 'orderId.android.test.purchased'
                }
            }
            self._assert_response({'error': 'An error occurred during order creation.'})
            self.assertTrue(fake_handle_order_placement.called)
            logger.check(
                (self.DUPLICATE_ORDER_LOGGER_NAME, 'ERROR', self.order_placement_error_message)
            )

    def test_duplicate_order_attempt_logging(self):
        """
        Verify that attempts at creation of a duplicate order are logged correctly
        """
        prior_order = create_order()
        dummy_view = MobileCoursePurchaseExecutionView()
        self.request.site = self.site
        dummy_view.request = self.request

        with LogCapture(self.DUPLICATE_ORDER_LOGGER_NAME) as log_capture, self.assertRaises(Exception):
            dummy_view.create_order(request=self.request, basket=prior_order.basket)
            log_capture.check(
                (
                    self.DUPLICATE_ORDER_LOGGER_NAME,
                    'ERROR',
                    self.get_duplicate_order_error_message(payment_processor='Paypal', order=prior_order)
                ),
            )

    def test_payment_error_with_no_basket(self):
        """
        Verify that we fail gracefully when any Exception occurred in _get_basket() method,
        logging the exception.
        """
        dummy_basket_id = self.basket.id + 1
        self.post_data['basket_id'] = dummy_basket_id
        with LogCapture(self.logger_name) as logger:
            self._assert_response({'error': ERROR_BASKET_NOT_FOUND.format(dummy_basket_id)})
            logger.check(
                (
                    self.logger_name,
                    'INFO',
                    LOGGER_EXECUTE_STARTED % (self.user.username, dummy_basket_id, self.processor_name)
                ),
                (
                    self.logger_name,
                    'ERROR',
                    LOGGER_BASKET_NOT_FOUND % (dummy_basket_id, self.user.username)
                )
            )

    def test_iap_payment_execution_ios(self):
        """
        Verify that a user gets successful response if payment is handled correctly and
        order is created successfully.
        """
        ios_post_data = self.post_data
        ios_post_data['payment_processor'] = IOSIAP(self.site).NAME
        with mock.patch.object(IOSValidator, 'validate') as fake_ios_validation:
            with LogCapture(self.logger_name) as logger:
                fake_ios_validation.return_value = {
                    'receipt': {
                        'in_app': [{
                            'original_transaction_id': '123456',
                            'transaction_id': '123456',
                            'product_id': 'fake_product_id'
                        }]
                    }
                }
                response = self.client.post(self.path, data=ios_post_data)
                order = Order.objects.get(number=self.basket.order_number)
                self.assertEqual(response.json(), {'order_data': MobileOrderSerializer(order).data})
                logger.check(
                    (
                        self.logger_name,
                        'INFO',
                        LOGGER_EXECUTE_STARTED % (self.user.username, self.basket.id,
                                                  ios_post_data['payment_processor'])
                    ),
                    (
                        self.logger_name,
                        'INFO',
                        LOGGER_EXECUTE_SUCCESSFUL % (self.user.username, self.basket.id,
                                                     ios_post_data['payment_processor'])
                    )
                )

    def test_iap_payment_execution_android(self):
        """
        Verify that a user gets successful response if payment is handled correctly and
        order is created successfully for Android.
        """
        with mock.patch.object(GooglePlayValidator, 'validate') as fake_google_validation, \
                LogCapture(self.logger_name) as logger:
            fake_google_validation.return_value = {
                'resource': {
                    'orderId': 'orderId.android.test.purchased'
                }
            }
            response = self.client.post(self.path, data=self.post_data)
            order = Order.objects.get(number=self.basket.order_number)
            self.assertEqual(response.json(), {'order_data': MobileOrderSerializer(order).data})
            logger.check(
                (
                    self.logger_name,
                    'INFO',
                    LOGGER_EXECUTE_STARTED % (self.user.username, self.basket.id, self.processor_name)
                ),
                (
                    self.logger_name,
                    'INFO',
                    LOGGER_EXECUTE_SUCCESSFUL % (self.user.username, self.basket.id, self.processor_name)
                )
            )

    def test_iap_payment_execution_basket_id_error(self):
        """
        Verify that a message is returned if basket_id is missing in
        """
        missing_basket_id_post_data = self.post_data
        missing_basket_id_post_data.pop('basket_id')
        error_message = '"{}"'.format(ERROR_BASKET_ID_NOT_PROVIDED)
        error_response = '{"error": ' + error_message + '}'
        expected_response = error_response.encode('UTF-8')
        expected_response_status_code = 400
        with mock.patch.object(GooglePlayValidator, 'validate') as fake_google_validation:
            fake_google_validation.return_value = {
                'resource': {
                    'orderId': 'orderId.android.test.purchased'
                }
            }
            response = self.client.post(self.path, data=missing_basket_id_post_data)
            self.assertEqual(response.status_code, expected_response_status_code)
            self.assertEqual(response.content, expected_response)

    @mock.patch('ecommerce.extensions.checkout.mixins.EdxOrderPlacementMixin.handle_payment')
    def test_redundant_payment_notification_error(self, mock_handle_payment):
        mock_handle_payment.side_effect = RedundantPaymentNotificationError()
        expected_response_status_code = 409
        error_message = COURSE_ALREADY_PAID_ON_DEVICE.encode('UTF-8')
        expected_response_content = b'{"error": "%s"}' % error_message
        with mock.patch.object(GooglePlayValidator, 'validate') as fake_google_validation, \
                LogCapture(self.logger_name) as logger:
            fake_google_validation.return_value = {
                'resource': {
                    'orderId': 'orderId.android.test.purchased'
                }
            }
            response = self.client.post(self.path, data=self.post_data)
            self.assertTrue(mock_handle_payment.called)
            self.assertEqual(response.status_code, expected_response_status_code)
            self.assertEqual(response.content, expected_response_content)
            logger.check(
                (
                    self.logger_name,
                    'INFO',
                    LOGGER_EXECUTE_STARTED % (self.user.username, self.basket.id, self.processor_name)
                ),
                (
                    self.logger_name,
                    'ERROR',
                    LOGGER_EXECUTE_REDUNDANT_PAYMENT % (self.user.username, self.basket.id)
                ),
            )

    @mock.patch('ecommerce.extensions.checkout.mixins.EdxOrderPlacementMixin.handle_post_order')
    def test_post_order_exception(self, mock_handle_post_order):
        mock_handle_post_order.side_effect = AttributeError()
        expected_response_status_code = 200
        error_message = ERROR_DURING_POST_ORDER_OP.encode('UTF-8')
        expected_response_content = b'{"error": "%s"}' % error_message
        with mock.patch.object(GooglePlayValidator, 'validate') as fake_google_validation:
            fake_google_validation.return_value = {
                'resource': {
                    'orderId': 'orderId.android.test.purchased'
                }
            }
            response = self.client.post(self.path, data=self.post_data)
            self.assertTrue(mock_handle_post_order.called)
            self.assertEqual(response.status_code, expected_response_status_code)
            self.assertEqual(response.content, expected_response_content)

    def test_already_purchased_basket(self):
        with mock.patch.object(GooglePlayValidator, 'validate') as fake_google_validation:
            fake_google_validation.return_value = {
                'resource': {
                    'orderId': 'orderId.android.test.purchased'
                }
            }
            with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=True), \
                    LogCapture(self.logger_name) as logger:
                create_order(site=self.site, user=self.user, basket=self.basket)
                response = self.client.post(self.path, data=self.post_data)
                self.assertEqual(response.status_code, 406)
                self.assertEqual(response.json().get('error'), ERROR_ALREADY_PURCHASED)
                logger.check(
                    (
                        self.logger_name,
                        'INFO',
                        LOGGER_EXECUTE_STARTED % (self.user.username, self.basket.id, self.processor_name)
                    ),
                    (
                        self.logger_name,
                        'ERROR',
                        LOGGER_EXECUTE_ALREADY_PURCHASED % (self.user.username, self.basket.id)
                    ),
                )


class TestMobileCheckoutView(TestCase):
    """ Tests for MobileCheckoutView API view. """
    path = reverse('iap:iap-checkout')

    def setUp(self):
        super(TestMobileCheckoutView, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory(partner=self.partner)
        product = self.course.create_or_update_seat('verified', False, 50)
        self.basket = create_basket(
            owner=self.user, site=self.site, price='50.0', product_class=product.product_class
        )

        self.processor = AndroidIAP(self.site)
        self.processor_name = self.processor.NAME

        self.post_data = {
            'basket_id': self.basket.id,
            'payment_processor': 'android-iap'
        }

    def test_authentication_required(self):
        """ Verify the endpoint requires authentication. """
        self.client.logout()
        response = self.client.post(self.path, data=self.post_data)
        self.assertEqual(response.status_code, 401)

    def test_no_basket(self):
        """ Verify the endpoint returns HTTP 400 if the user has no associated baskets. """
        self.user.baskets.all().delete()
        expected_content = b'{"error": "Basket [%s] not found."}' % str(self.post_data['basket_id']).encode()
        response = self.client.post(self.path, data=self.post_data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, expected_content)

    @override_settings(
        PAYMENT_PROCESSORS=['ecommerce.extensions.iap.processors.android_iap.AndroidIAP']
    )
    def test_view_response(self):
        """ Verify the endpoint returns a successful response when the user is able to checkout. """
        toggle_switch(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + self.processor_name, True)
        response = self.client.post(self.path, data=self.post_data)
        self.assertEqual(response.status_code, 200)

        basket = Basket.objects.get(id=self.basket.id)
        self.assertEqual(basket.status, Basket.FROZEN)
        response_data = response.json()
        self.assertIn(reverse('iap:iap-execute'), response_data['payment_page_url'])
        self.assertEqual(response_data['payment_processor'], self.processor_name)


class BaseRefundTests(RefundTestMixin, AccessTokenMixin, JwtMixin, TestCase):
    MODEL_LOGGER_NAME = 'ecommerce.core.models'

    def setUp(self):
        super(BaseRefundTests, self).setUp()
        self.course_id = 'edX/DemoX/Demo_Course'
        self.invalid_transaction_id = "invalid transaction"
        self.valid_transaction_id = "123456"
        self.entitlement_option = Option.objects.get(code='course_entitlement')
        self.user = self.create_user()
        self.logger_name = 'ecommerce.extensions.iap.api.v1.views'

    def assert_ok_response(self, response):
        """ Assert the response has HTTP status 200 and no data. """
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_transaction_id_not_found(self):
        """ If the transaction id doesn't match, no refund IDs should be created. """
        with LogCapture(self.logger_name) as logger:
            AndroidRefundView().refund(self.invalid_transaction_id, {})
            msg = ERROR_TRANSACTION_NOT_FOUND_FOR_REFUND % (self.invalid_transaction_id,
                                                            AndroidRefundView.processor_name)
            logger.check((self.logger_name, 'ERROR', msg),)

    @staticmethod
    def _revoke_lines(refund):
        for line in refund.lines.all():
            line.set_status(REFUND_LINE.COMPLETE)

        refund.set_status(REFUND.COMPLETE)

    def assert_refund_and_order(self, refund, order, basket, processor_response, refund_response):
        """ Check if we refunded the correct order """
        self.assertEqual(refund.order, order)
        self.assertEqual(refund.user, order.user)
        self.assertEqual(refund.status, 'Complete')
        self.assertEqual(refund.total_credit_excl_tax, order.total_excl_tax)
        self.assertEqual(refund.lines.count(), order.lines.count())

        self.assertEqual(basket, processor_response.basket)
        self.assertEqual(refund_response.transaction_id, processor_response.transaction_id)

    def test_refund_completion_error(self):
        """
        View should create a refund if an order/line are found eligible for refund.
        """
        order = self.create_order()
        PaymentProcessorResponse.objects.create(basket=order.basket,
                                                transaction_id=self.valid_transaction_id,
                                                processor_name=AndroidRefundView.processor_name,
                                                response=json.dumps({'state': 'approved'}))

        def _revoke_lines(refund):
            for line in refund.lines.all():
                line.set_status(REFUND_LINE.COMPLETE)

            refund.set_status(REFUND.REVOCATION_ERROR)

        with mock.patch.object(Refund, '_revoke_lines', side_effect=_revoke_lines, autospec=True):
            refund_payload = {"state": "refund"}
            msg = ERROR_REFUND_NOT_COMPLETED % (self.user.username, self.course_id, AndroidRefundView.processor_name)

            with LogCapture(self.logger_name) as logger:
                AndroidRefundView().refund(self.valid_transaction_id, refund_payload)
                self.assertFalse(Refund.objects.exists())
                self.assertEqual(len(PaymentProcessorResponse.objects.all()), 1)
                # logger.check((self.logger_name, 'ERROR', msg),)

                # A second call should ensure the atomicity of the refund logic
                AndroidRefundView().refund(self.valid_transaction_id, refund_payload)
                self.assertFalse(Refund.objects.exists())
                self.assertEqual(len(PaymentProcessorResponse.objects.all()), 1)
                logger.check(
                    (self.logger_name, 'ERROR', msg),
                    (self.logger_name, 'ERROR', msg)
                )

    def test_valid_order(self):
        """
        View should create a refund if an order/line are found eligible for refund.
        """
        order = self.create_order()
        basket = order.basket
        self.assertFalse(Refund.objects.exists())
        processor_response = PaymentProcessorResponse.objects.create(basket=basket,
                                                                     transaction_id=self.valid_transaction_id,
                                                                     processor_name=AndroidRefundView.processor_name,
                                                                     response=json.dumps({'state': 'approved'}))

        with mock.patch.object(Refund, '_revoke_lines', side_effect=BaseRefundTests._revoke_lines, autospec=True):
            refund_payload = {"state": "refund"}
            AndroidRefundView().refund(self.valid_transaction_id, refund_payload)
            refund = Refund.objects.latest()
            refund_response = PaymentProcessorResponse.objects.latest()

            self.assert_refund_and_order(refund, order, basket, processor_response, refund_response)

            # A second call should result in no additional refunds being created
            with LogCapture(self.logger_name) as logger:
                AndroidRefundView().refund(self.valid_transaction_id, {})
                msg = ERROR_ORDER_NOT_FOUND_FOR_REFUND % (self.valid_transaction_id, AndroidRefundView.processor_name)
                logger.check((self.logger_name, 'ERROR', msg),)


class AndroidRefundTests(BaseRefundTests):
    path = reverse('iap:android-refund')
    order_id_one = "1234"
    order_id_two = "5678"
    mock_processor_response = {
        "voidedPurchases": [
            {
                "purchaseToken": "purchase_token",
                "purchaseTimeMillis": "1677275637963",
                "voidedTimeMillis": "1677650787656",
                "orderId": order_id_one,
                "voidedSource": 1,
                "voidedReason": 1,
                "kind": "androidpublisher#voidedPurchase"
            },
            {
                "purchaseToken": "purchase_token",
                "purchaseTimeMillis": "1674131262110",
                "voidedTimeMillis": "1677671872090",
                "orderId": order_id_two,
                "voidedSource": 0,
                "voidedReason": 0,
                "kind": "androidpublisher#voidedPurchase"
            }
        ]
    }
    logger_name = 'ecommerce.extensions.iap.api.v1.views'
    processor_name = AndroidIAP.NAME

    def check_record_not_found_log(self, logger, msg_t):
        response = self.client.get(self.path)
        self.assert_ok_response(response)
        refunds = self.mock_processor_response['voidedPurchases']
        msgs = [msg_t % (refund['orderId'], self.processor_name) for refund in refunds]
        logger.check(
            (self.logger_name, 'ERROR', msgs[0]),
            (self.logger_name, 'ERROR', msgs[1])
        )

    def test_transaction_id_not_found(self):
        """ If the transaction id doesn't match, no refund IDs should be created. """

        with mock.patch.object(ServiceAccountCredentials, 'from_json_keyfile_dict') as mock_credential_method, \
                mock.patch('ecommerce.extensions.iap.api.v1.views.build') as mock_build, \
                LogCapture(self.logger_name) as logger, \
                mock.patch('httplib2.Http'):

            mock_credential_method.return_value.authorize.return_value = None
            mock_build.return_value.purchases.return_value.voidedpurchases.return_value\
                .list.return_value.execute.return_value = self.mock_processor_response
            self.check_record_not_found_log(logger, ERROR_TRANSACTION_NOT_FOUND_FOR_REFUND)

    def test_valid_orders(self):
        """
        View should create a refund if an order/line are found eligible for refund.
        """
        orders = [self.create_order()]
        self.assertFalse(Refund.objects.exists())
        baskets = [BasketFactory(site=self.site, owner=self.user)]
        baskets[0].add_product(self.verified_product)

        second_course = CourseFactory(
            id=u'edX/DemoX/Demo_Coursesecond', name=u'edX Demó Course second', partner=self.partner
        )
        second_verified_product = second_course.create_or_update_seat('verified', True, 10)
        baskets.append(BasketFactory(site=self.site, owner=self.user))
        baskets[1].add_product(second_verified_product)
        orders.append(create_order(basket=baskets[1], user=self.user))
        orders[1].status = ORDER.COMPLETE

        payment_processor_responses = []
        for index in range(len(baskets)):
            transaction_id = self.mock_processor_response['voidedPurchases'][index]['orderId']
            payment_processor_responses.append(
                PaymentProcessorResponse.objects.create(basket=baskets[0], transaction_id=transaction_id,
                                                        processor_name=AndroidRefundView.processor_name,
                                                        response=json.dumps({'state': 'approved'})))

        with mock.patch.object(Refund, '_revoke_lines', side_effect=BaseRefundTests._revoke_lines, autospec=True), \
             mock.patch.object(ServiceAccountCredentials, 'from_json_keyfile_dict') as mock_credential_method, \
                mock.patch('ecommerce.extensions.iap.api.v1.views.build') as mock_build, \
                mock.patch('httplib2.Http'), \
                LogCapture(self.logger_name) as logger:

            mock_credential_method.return_value.authorize.return_value = None
            mock_build.return_value.purchases.return_value.voidedpurchases.return_value.\
                list.return_value.execute.return_value = self.mock_processor_response

            response = self.client.get(self.path)
            self.assert_ok_response(response)
            logger.check(
                (
                    self.logger_name,
                    'INFO',
                    LOGGER_REFUND_SUCCESSFUL % (self.order_id_one, self.processor_name)
                ),
                (
                    self.logger_name,
                    'ERROR',
                    ERROR_ORDER_NOT_FOUND_FOR_REFUND % (self.order_id_two, self.processor_name)
                )

            )

            refunds = Refund.objects.all()
            refund_responses = PaymentProcessorResponse.objects.all().order_by('-id')[:1]
            for index, _ in enumerate(refunds):
                self.assert_refund_and_order(refunds[index], orders[index], baskets[index],
                                             payment_processor_responses[index], refund_responses[index])

            # A second call should result in no additional refunds being created
            with LogCapture(self.logger_name) as logger:
                self.check_record_not_found_log(logger, ERROR_ORDER_NOT_FOUND_FOR_REFUND)


class IOSRefundTests(BaseRefundTests):
    path = reverse('iap:ios-refund')
    order_id_one = "1234"
    mock_processor_response = {
        "notificationType": "REFUND",
        "notificationUUID": "3e16e420",
        "data": {
            "bundleId": "test.mobile",
            "environment": "Sandbox",
            "signedTransactionInfo": {
                "originalTransactionId": "1234"
            }
        },
        "version": "2.0",
        "signedDate": 1679801012716
    }
    logger_name = 'ecommerce.extensions.iap.api.v1.views'
    processor_name = IOSIAP.NAME

    def assert_error_response(self, response):
        """ Assert the response has HTTP status 200 and no data. """
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def check_record_not_found_log(self, logger, msg_t):
        response = self.client.post(self.path)
        self.assert_error_response(response)
        transaction = self.mock_processor_response['data']['signedTransactionInfo']['originalTransactionId']
        msg = msg_t % (transaction, self.processor_name)
        info = RECEIVED_NOTIFICATION_FROM_APPLE % "REFUND"
        logger.check(
            (self.logger_name, "INFO", info),
            (self.logger_name, 'ERROR', msg)
        )

    def test_transaction_id_not_found(self):
        """ If the transaction id doesn't match, no refund IDs should be created. """

        with mock.patch.object(asn2, 'parse') as mock_ios_response_parse, \
                LogCapture(self.logger_name) as logger:

            mock_ios_response_parse.return_value = self.mock_processor_response
            self.check_record_not_found_log(logger, ERROR_TRANSACTION_NOT_FOUND_FOR_REFUND)

    def test_valid_orders(self):
        """
        View should create a refund if an order/line are found eligible for refund.
        """
        order = self.create_order()
        self.assertFalse(Refund.objects.exists())
        basket = BasketFactory(site=self.site, owner=self.user)
        basket.add_product(self.verified_product)

        transaction_id = self.mock_processor_response['data']['signedTransactionInfo']['originalTransactionId']
        processor_response = PaymentProcessorResponse.objects.create(basket=basket, transaction_id=transaction_id,
                                                                     processor_name=self.processor_name,
                                                                     response=json.dumps(self.mock_processor_response))

        with mock.patch.object(Refund, '_revoke_lines', side_effect=BaseRefundTests._revoke_lines, autospec=True), \
                mock.patch.object(asn2, 'parse') as mock_ios_response_parse, \
                LogCapture(self.logger_name) as logger:

            mock_ios_response_parse.return_value = self.mock_processor_response
            response = self.client.post(self.path)
            self.assert_ok_response(response)
            logger.check(
                (
                    self.logger_name,
                    'INFO',
                    RECEIVED_NOTIFICATION_FROM_APPLE % "REFUND"
                ),
                (
                    self.logger_name,
                    'INFO',
                    LOGGER_REFUND_SUCCESSFUL % (self.order_id_one, self.processor_name)
                ),
            )

            refunds = Refund.objects.all()
            refund_responses = PaymentProcessorResponse.objects.all()
            self.assertEqual(len(refunds), 1)
            self.assert_refund_and_order(refunds[0], order, basket,
                                         processor_response, refund_responses[0])

            # A second call should result in no additional refunds being created
            with LogCapture(self.logger_name) as logger:
                self.check_record_not_found_log(logger, ERROR_ORDER_NOT_FOUND_FOR_REFUND)

    def test_non_refund_notification(self):
        """
        View should create a refund if an order/line are found eligible for refund.
        """

        with mock.patch.object(asn2, 'parse') as mock_ios_response_parse,\
                LogCapture(self.logger_name) as logger:

            non_refund_payload = self.mock_processor_response.copy()
            non_refund_payload['notificationType'] = 'TEST'
            mock_ios_response_parse.return_value = non_refund_payload
            response = self.client.post(self.path)
            self.assert_ok_response(response)
            logger.check(
                (
                    self.logger_name,
                    'INFO',
                    RECEIVED_NOTIFICATION_FROM_APPLE % "TEST"
                ),
                (
                    self.logger_name,
                    'INFO',
                    IGNORE_NON_REFUND_NOTIFICATION_FROM_APPLE
                )
            )
