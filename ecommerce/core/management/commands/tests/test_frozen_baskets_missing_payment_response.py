"""
Tests for Django management command to verify ecommerce transactions.
"""
from __future__ import absolute_import

import datetime

import pytz
from django.core.management import call_command
from django.test.utils import override_settings
from ecommerce.tests.testcases import TestCase
from oscar.test.factories import OrderFactory, OrderLineFactory, ProductFactory
from mock import patch, Mock


from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, Subquery
from oscar.core.loading import get_class, get_model
#from ecommerce.extensions.partner.strategy import DefaultStrategy

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
BillingAddress = get_model('order', 'BillingAddress')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')
Country = get_model('address', 'Country')
OrderCreator = get_class('order.utils', 'OrderCreator')
SiteConfiguration = get_model('core', 'SiteConfiguration')
from ecommerce.extensions.basket.tests.mixins import BasketMixin
from ecommerce.tests.factories import SiteConfigurationFactory, UserFactory
LOGGER_NAME = 'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response'
from testfixtures import LogCapture
import json


class FrozenBasketMissingResponseTest(BasketMixin, TestCase):

    def setUp(self):
        super(FrozenBasketMissingResponseTest, self).setUp()
        self.basket = self.create_basket(self.create_user(), self.site)
        self.start_delta = 4
        self.end_delta = 0

        self.search_transaction_json = {
            "_embedded": {
                "transactionSummaries": [
                    {
                        "id": "559733",
                        "submitTimeUtc": "2019-06-05T11:14:28Z",
                        "merchantId": "test_edx_org",
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

                    }]
            }
        }
        self.transaction_detail = {

        }
        self.basket.save()

    @override_settings(CS_API_CONFIG={'host': 'apitest.cybersource.com', 'merchant_id': 'edx_org',
                                      'API_KEY_ID': None, 'API_KEY_SECRET': None})
    def test_invalid_configuration(self):
        commands_args = [
            '--start-delta={}'.format(self.start_delta),
            '--end-delta={}'.format(self.end_delta)
        ]
        with self.assertRaises(CommandError) as cm:
            call_command('find_frozen_baskets_missing_payment_response', *commands_args)
        exception = cm.exception
        self.assertIn(u"Missing API Key ID/KeySecret in configuration", exception.message)


    def test_no_frozen_basket_missing_response(self):

        commands_args = [
            '--start-delta={}'.format(self.start_delta),
            '--end-delta={}'.format(self.end_delta)
        ]

        with LogCapture(LOGGER_NAME) as l:
            call_command('find_frozen_baskets_missing_payment_response', *commands_args)
            l.check(
                (LOGGER_NAME, 'INFO', u"No frozen baskets, missing payment response found")
            )

    def test_cybersource_transaction_search_success(self):

        self.basket.status = Basket.FROZEN
        self.basket.save()

        commands_args = [
            '--start-delta={}'.format(self.start_delta),
            '--end-delta={}'.format(self.end_delta)
        ]


        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:

                post_response = Mock()
                post_response.status_code = 201
                post_response.content = self.search_transaction_json
                mock_requests.post.return_value = post_response

                call_command('find_frozen_baskets_missing_payment_response', *commands_args)
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
                )

    def test_cybersource_transaction_search_failure(self):

        self.basket.status = Basket.FROZEN
        self.basket.save()

        commands_args = [
            '--start-delta={}'.format(self.start_delta),
            '--end-delta={}'.format(self.end_delta)
        ]
        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:

                post_response = Mock()
                post_response.status_code = 404
                post_response.content = {}
                mock_requests.post.return_value = post_response

                call_command('find_frozen_baskets_missing_payment_response', *commands_args)
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

    def test_cybersource_transaction_search_invalid_response(self):

        self.basket.status = Basket.FROZEN
        self.basket.save()

        commands_args = [
            '--start-delta={}'.format(self.start_delta),
            '--end-delta={}'.format(self.end_delta)
        ]

        with LogCapture(LOGGER_NAME) as l:
            with patch(
                    'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response.requests') as mock_requests:

                post_response = Mock()
                post_response.status_code = 201
                post_response.content = json.dumps({})
                mock_requests.post.return_value = post_response

                call_command('find_frozen_baskets_missing_payment_response', *commands_args)

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
                        LOGGER_NAME, 'ERROR',
                        u"Some information was not found in meta from CyberSource "
                        u"Transaction Search api for Order Number: {}".format(
                            self.basket.order_number
                        )
                    ),
                )



    def test_cybsersource_transaction_detail_response(self):
        pass


    def test_no_order_created_if_exists(self):
        pass