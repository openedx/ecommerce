"""
Tests for Django management command to verify ecommerce transactions.
"""
from __future__ import absolute_import

import json

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test.utils import override_settings
from mock import Mock, patch
from oscar.core.loading import get_class, get_model
from testfixtures import LogCapture

from ecommerce.extensions.basket.tests.mixins import BasketMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
BillingAddress = get_model('order', 'BillingAddress')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
Country = get_model('address', 'Country')
OrderCreator = get_class('order.utils', 'OrderCreator')
SiteConfiguration = get_model('core', 'SiteConfiguration')

LOGGER_NAME = 'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response'


class FrozenBasketMissingResponseTest(BasketMixin, TestCase):

    def setUp(self):
        super(FrozenBasketMissingResponseTest, self).setUp()

        self.user = self.create_user()
        self.basket = self.create_basket(self.user, self.site)
        self.start_delta = 4
        self.end_delta = 0

        Country.objects.create(iso_3166_1_a2='AE',
                              iso_3166_1_a3='ARE',
                              iso_3166_1_numeric=784,
                              printable_name='United Arab Emirates',
                              name='',
                              display_order=0,
                              is_shipping_country=True)

        self.commands_args = [
            '--start-delta={}'.format(self.start_delta),
            '--end-delta={}'.format(self.end_delta)
        ]

        self.search_transaction = {
            "_embedded": {
                "transactionSummaries": [
                    {
                        "id": "559733",
                        "submitTimeUtc": "2019-06-05T11:14:28Z",
                        "merchantId": "test_merchant",
                        "applicationInformation": {
                            "applications": [
                                {
                                    "name": "ics_auth",
                                    "reasonCode": "100",
                                    "rCode": "1",
                                    "rMessage": "Request was processed successfully."
                                },
                                {
                                    "name": "ics_bill",
                                    "reasonCode": "100",
                                    "rCode": "1",
                                    "rMessage": "Request was processed successfully."
                                }
                            ]
                        },
                        "_links": {
                            "transactionDetail": {
                                "href": "https://test.cybersource.com:-1/tss/v2/transactions/5597",
                                "method": "GET"
                            }
                        }
                    }]
            }
        }

        self.transaction_detail = {
            "merchantId": "test_merchant",
            "applicationInformation": {
                "status": "TRANSMITTED",
                "reasonCode": 100,
                "applications": [
                    {
                        "name": "ics_auth",
                        "reasonCode": "100",
                        "rCode": "1",
                        "rFlag": "SOK",
                        "rMessage": "Request was processed successfully.",
                    },
                    {
                        "name": "ics_bill",
                        "status": "TRANSMITTED",
                        "reasonCode": "100",
                        "rMessage": "Request was processed successfully.",
                    },
                ]
            },
            "buyerInformation": {},
            "orderInformation": {
                "billTo": {
                    "firstName": "Yasir",
                    "lastName": "Bashir",
                    "address1": "abc",
                    "locality": "abc",
                    "administrativeArea": "N/A",
                    "postalCode": "123456",
                    "email": "edx@test.com",
                    "country": "AE"
                },
                "shipTo": {},
                "amountDetails": {
                    "totalAmount": "400",
                    "currency": "USD",
                    "taxAmount": "0",
                    "authorizedAmount": "400"
                },
                "shippingDetails": {},
            },
        }

        self.basket.status = Basket.FROZEN
        self.basket.save()

    @override_settings(CS_API_CONFIG={'host': 'apitest.cybersource.com', 'merchant_id': 'test_merchant',
                                      'API_KEY_ID': None, 'API_KEY_SECRET': None})
    def test_invalid_configuration(self):

        with self.assertRaises(CommandError) as cm:
            call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)
        exception = cm.exception
        self.assertIn(u"Missing API Key ID/KeySecret in configuration", exception.message)

    def test_no_frozen_basket_missing_response(self):

        self.basket.status = Basket.OPEN
        self.basket.save()

        with LogCapture(LOGGER_NAME) as l:
            call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)
            l.check(
                (LOGGER_NAME, 'INFO', u"No frozen baskets, missing payment response found")
            )

    def test_invalid_time_range(self):

        self.start_delta = 2
        self.end_delta = 3

        self.commands_args = [
            '--start-delta={}'.format(self.start_delta),
            '--end-delta={}'.format(self.end_delta)
        ]

        with LogCapture(LOGGER_NAME) as l:
            call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)
            l.check_present(
                (
                    LOGGER_NAME, 'ERROR',
                    u"Incorrect time range given."
                ),
            )

    def test_cybersource_transaction_search_response_success(self):

        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:

                post_response = Mock()
                post_response.status_code = 201
                post_response.content = json.dumps(self.search_transaction)
                mock_requests.post.return_value = post_response

                call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)
                l.check(
                    (
                        LOGGER_NAME, 'INFO',
                        u"Frozen baskets missing payment response found, checking with Cybersource.."
                    ),
                    (
                        LOGGER_NAME, 'INFO',
                        u"Basket ID " + str(self.basket.id) + u" Order Number " + self.basket.order_number
                    ),
                    (
                        LOGGER_NAME, 'INFO',
                        u"Checking Cybersource for orders: [{orders}]".format(orders=self.basket.order_number)
                    ),
                    (
                        LOGGER_NAME, 'INFO',
                        u"Response from CyberSource Transaction Search api successful for Order Number {}".format(
                         self.basket.order_number)
                    ),
                    (
                        LOGGER_NAME, 'INFO',
                        u"Successfully found meta information from CyberSource "
                        u"Transaction Search api for Order Number: {}".format(
                            self.basket.order_number)
                    ),
                )

    def test_cybersource_transaction_search_response_404(self):

        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:

                post_response = Mock()
                post_response.status_code = 404
                post_response.content = {}
                mock_requests.post.return_value = post_response

                call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)
                l.check(
                    (
                        LOGGER_NAME, 'INFO',
                        u"Frozen baskets missing payment response found, checking with Cybersource.."
                    ),
                    (
                        LOGGER_NAME, 'INFO',
                        u"Basket ID " + str(self.basket.id) + u" Order Number " + self.basket.order_number
                    ),
                    (
                        LOGGER_NAME, 'INFO',
                        u"Checking Cybersource for orders: [{orders}]".format(orders=self.basket.order_number)
                    ),
                    (
                        LOGGER_NAME, 'INFO',
                        u"Response from CyberSource Transaction Search api unsuccessful for Order Number {}".format(
                        self.basket.order_number)
                    ),
                )

    def test_cybersource_transaction_search_information_missing(self):

        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:

                post_response = Mock()
                post_response.status_code = 201
                post_response.content = json.dumps({})
                mock_requests.post.return_value = post_response

                call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)

                l.check_present(
                    (
                        LOGGER_NAME, 'ERROR',
                        u"Some information was not found in meta from CyberSource "
                        u"Transaction Search api for Order Number: {}".format(
                            self.basket.order_number
                        )
                    ),
                )

    def test_cybersource_transaction_search_summary_info_missing(self):

        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:

                post_response = Mock()
                post_response.status_code = 201
                post_response.content = json.dumps({
                    "_embedded": {
                        "transactionSummaries": []
                    }
                })
                mock_requests.post.return_value = post_response

                call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)

                l.check_present(
                    (
                        LOGGER_NAME, 'INFO',
                        u"No summary info found from CyberSource "
                        u"Transaction Search api for Order Number: {}".format(self.basket.order_number)
                    ),
                )

    @patch('ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.fulfill_order')
    @patch('ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests')
    def test_cybsersource_transaction_detail_response_success(self, mock_requests, mock_fullfill_order):

        with LogCapture(LOGGER_NAME) as l:

            post_response = Mock()
            post_response.status_code = 201
            post_response.content = json.dumps(self.search_transaction)
            mock_requests.post.return_value = post_response

            get_response = Mock()
            get_response.status_code = 200
            get_response.content = json.dumps(self.transaction_detail)
            mock_requests.get.return_value = get_response

            call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)
            l.check_present(
                (
                    LOGGER_NAME, 'INFO',
                    u"Successfully found transaction information from CyberSource "
                    u"Transaction api for Order Number: " + self.basket.order_number
                ),
                (
                    LOGGER_NAME, 'INFO',
                    u"Processing Order Number: {order_number} for order creation."
                        .format(order_number=self.basket.order_number)
                ),
                (
                    LOGGER_NAME, 'INFO',
                    u"Order Number: {order_number} doesn't exist, creating it."
                        .format(order_number=self.basket.order_number)
                ),
                (
                    LOGGER_NAME, 'INFO',
                    u"Order Number: {order_number} created successfully."
                        .format(order_number=self.basket.order_number)
                ),
            )

            basket = Basket.objects.get(pk=self.basket.id)
            self.assertEqual(basket.status, Basket.SUBMITTED)
            self.assertTrue(Order.objects.filter(number=basket.order_number).exists())


    def test_cybsersource_transaction_detail_response_failure(self):

        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:

                post_response = Mock()
                post_response.status_code = 201
                post_response.content = json.dumps(self.search_transaction)
                mock_requests.post.return_value = post_response

                get_response = Mock()
                get_response.status_code = 200
                self.transaction_detail['applicationInformation']= {
                    "reasonCode": "102",
                    'applications':[
                        {
                            "name": "ics_auth",
                            "reasonCode": "102",
                        },
                        {
                            "name": "ics_bill",
                            "reasonCode": "102",
                        }
                    ]
                }
                get_response.content = json.dumps(self.transaction_detail)
                mock_requests.get.return_value = get_response


                call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)
                l.check_present(
                    (
                        LOGGER_NAME, 'INFO',
                        u"CS Transaction information shows unsucccessful transaction logged for Order Number " +
                        self.basket.order_number
                    ),

                )

    def test_cybsersource_transaction_detail_application_summary_info_missing(self):

        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:

                post_response = Mock()
                post_response.status_code = 201
                post_response.content = json.dumps(self.search_transaction)
                mock_requests.post.return_value = post_response

                get_response = Mock()
                get_response.status_code = 200
                self.transaction_detail['applicationInformation'] = {}
                get_response.content = json.dumps(self.transaction_detail)
                mock_requests.get.return_value = get_response


                call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)
                l.check_present(
                    (
                        LOGGER_NAME, 'INFO',
                        u"Application summary information missing from transaction detail response "
                        u"for Order Number: " + self.basket.order_number
                    )
                )

    def test_cybsersource_transaction_response_order_info_missing(self):

        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:

                post_response = Mock()
                post_response.status_code = 201
                post_response.content = json.dumps(self.search_transaction)
                mock_requests.post.return_value = post_response

                get_response = Mock()
                get_response.status_code = 200

                self.transaction_detail['orderInformation'] = {}

                get_response.content = json.dumps(self.transaction_detail)
                mock_requests.get.return_value = get_response


                call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)
                l.check_present(
                    (
                        LOGGER_NAME, 'INFO',
                        u"No order information found in transaction detail json "
                        u"for Order Number: " + self.basket.order_number
                    ),
                )

    def test_cybsersource_transaction_detail_raise_exception(self):

        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:
                post_response = Mock()
                post_response.status_code = 201
                post_response.content = json.dumps(self.search_transaction)
                mock_requests.post.return_value = post_response

                get_response = Mock()
                get_response.status_code = 200
                exception_msg = 'exception msg'
                mock_requests.get.side_effect = Exception(exception_msg)

                call_command('find_frozen_baskets_missing_payment_response', *self.commands_args)
                l.check_present(
                    (
                        LOGGER_NAME, 'ERROR',
                        u'Exception occurred while fetching transaction detail for Order Number' 
                             u'from Transaction api: [{}]: {}'.format(self.basket.order_number, exception_msg)
                    ),
                )
