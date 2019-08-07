""" AuthorizeNet payment processor. """
from __future__ import absolute_import, unicode_literals

import logging
import requests
import json
from oscar.apps.payment.exceptions import TransactionDeclined
from oscar.core.loading import get_model

from ecommerce.extensions.payment.processors import (
    BaseClientSidePaymentProcessor,
    HandledProcessorResponse
)
from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.core.url_utils import get_lms_dashboard_url
from urlparse import urljoin
from oscar.apps.payment.exceptions import GatewayError

import os, sys
from authorizenet import apicontractsv1
from authorizenet.apicontrollers import *
from decimal import *

from django.urls import reverse

logger = logging.getLogger(__name__)

BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class AuthorizeNet(BaseClientSidePaymentProcessor):
    NAME = 'authorizenet'

    @property
    def payment_processor(self):
        return AuthorizeNet(self.request.site)

    def __init__(self, site):
        """
        Constructs a new instance of the AuthorizeNet processor.

        Raises:
            KeyError: If no settings configured for this payment processor.
        """
        super(AuthorizeNet, self).__init__(site)
        # self.basket = None

    @property
    def cancel_url(self):
        return get_ecommerce_url(self.configuration['cancel_checkout_path'])

    def _get_basket_amount(self, basket):
        return str((basket.total_incl_tax * 100).to_integral_value())

    def get_transaction_detail(self, transaction_id):
        merchantAuth = apicontractsv1.merchantAuthenticationType()
        merchantAuth.name = "78f4r3PmQH"
        merchantAuth.transactionKey = "5a2Paz7V84y8aGXj"

        transactionDetailsRequest = apicontractsv1.getTransactionDetailsRequest()
        transactionDetailsRequest.merchantAuthentication = merchantAuth
        transactionDetailsRequest.transId = transaction_id

        transactionDetailsController = getTransactionDetailsController(transactionDetailsRequest)
        transactionDetailsController.execute()

        transactionDetailsResponse = transactionDetailsController.getresponse()
        if transactionDetailsResponse is not None:
            if transactionDetailsResponse.messages.resultCode == apicontractsv1.messageTypeEnum.Ok:
                print('Successfully got transaction details!')
                print('Transaction Id : %s' % transactionDetailsResponse.transaction.transId)
                print('Transaction Type : %s' % transactionDetailsResponse.transaction.transactionType)
                print('Transaction Status : %s' % transactionDetailsResponse.transaction.transactionStatus)
                print('Auth Amount : %.2f' % transactionDetailsResponse.transaction.authAmount)
                print('Settle Amount : %.2f' % transactionDetailsResponse.transaction.settleAmount)

                if transactionDetailsResponse.messages is not None:
                    print('Message Code : %s' % transactionDetailsResponse.messages.message[0]['code'].text)
                    print('Message Text : %s' % transactionDetailsResponse.messages.message[0]['text'].text)
            else:
                if transactionDetailsResponse.messages is not None:
                    print('Failed to get transaction details.\nCode:%s \nText:%s' % (transactionDetailsResponse.messages.message[0]['code'].text,transactionDetailsResponse.messages.message[0]['text'].text))

        return transactionDetailsResponse

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=True, **kwargs):
        self.basket = basket
        return_url = get_lms_dashboard_url()

        merchantAuth = apicontractsv1.merchantAuthenticationType()
        merchantAuth.name = "78f4r3PmQH"
        merchantAuth.transactionKey = "5a2Paz7V84y8aGXj"

        setting1 = apicontractsv1.settingType()
        setting1.settingName = apicontractsv1.settingNameEnum.hostedPaymentButtonOptions
        setting1.settingValue = json.dumps({'text': 'Pay'})


        setting2 = apicontractsv1.settingType()
        setting2.settingName = apicontractsv1.settingNameEnum.hostedPaymentReturnOptions
        setting2_configrations = {
            'showReceipt': False,
            'url': return_url,
            'urlText': 'Continue',
            'cancelUrl': self.cancel_url,
            'cancelUrlText': 'Cancel'
        }
        setting2.settingValue = json.dumps(setting2_configrations)

        settings = apicontractsv1.ArrayOfSetting()
        settings.setting.append(setting1)
        settings.setting.append(setting2)

        order = apicontractsv1.orderType()
        order.invoiceNumber = basket.order_number
        order.description = "upgrade to verified"

        transactionrequest = apicontractsv1.transactionRequestType()
        transactionrequest.transactionType = "authCaptureTransaction"
        transactionrequest.amount = unicode(basket.total_incl_tax)
        transactionrequest.order = order

        line_items_list = apicontractsv1.ArrayOfLineItem()
        for line in basket.all_lines():
            line_item = apicontractsv1.lineItemType()
            line_item.itemId = line.product.course_id
            line_item.name = line.product.course_id
            line_item.description = line.product.title
            line_item.quantity = line.quantity
            line_item.unitPrice = unicode(line.line_price_incl_tax_incl_discounts / line.quantity)
            line_items_list.lineItem.append(line_item)

        paymentPageRequest = apicontractsv1.getHostedPaymentPageRequest()
        paymentPageRequest.merchantAuthentication = merchantAuth
        paymentPageRequest.transactionRequest = transactionrequest
        paymentPageRequest.hostedPaymentSettings = settings
        transactionrequest.lineItems = line_items_list

        paymentPageController = getHostedPaymentPageController(paymentPageRequest)
        paymentPageController.execute()

        paymentPageResponse = paymentPageController.getresponse()
        authorize_form_token = ""

        if paymentPageResponse is not None:
            if paymentPageResponse.messages.resultCode == apicontractsv1.messageTypeEnum.Ok:
                logger.info(
                    "%s [%d].",
                    "Successfully got hosted payment page for basket",
                    basket.id,
                    exc_info=True
                )
                authorize_form_token = str(paymentPageResponse.token)

            else:
                logger.error('Failed to get authorizenet payment token.')
                if paymentPageResponse.messages is not None:
                    logger.error(
                        '\nCode:%s \nText:%s' % (
                            paymentPageResponse.messages.message[0]['code'].text,
                            paymentPageResponse.messages.message[0]['text'].text
                        )
                    )
                raise GatewayError(paymentPageResponse.messages.message[0]['text'].text)
        else:
            logger.error(
                "%s [%d].",
                "Failed to create Authorizenet payment for basket",
                basket.id,
                exc_info=True
            )
            raise GatewayError('Authorizenet payment creation failure: unable to get Authorizenet form token')

        parameters = {
            'payment_page_url': 'https://test.authorize.net/payment/payment',
            'token': authorize_form_token
        }
        return parameters

    def handle_processor_response(self, transaction_response, basket=None):
        transaction_id = transaction_response.transaction.transId
        self.record_processor_response(transaction_response, transaction_id=transaction_id, basket=basket)
        logger.info("Successfully executed Authorizenet payment [%s] for basket [%d].", transaction_id, basket.id)

        currency = basket.currency
        total = Decimal(float(transaction_response.transaction.settleAmount))
        card_info = transaction_response.transaction.payment.creditCard

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=card_info.cardNumber,
            card_type=card_info.cardType
        )

    def issue_credit(
            self, order_number, basket, reference_number, amount, currency):
        pass
