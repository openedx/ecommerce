""" AuthorizeNet payment processor. """
from __future__ import absolute_import, unicode_literals

import base64
import logging
import json
from decimal import Decimal
from django.urls import reverse
from authorizenet import apicontractsv1
from authorizenet.apicontrollers import (
    getHostedPaymentPageController,
    getTransactionDetailsController,
    createTransactionController
)
from ecommerce.extensions.payment.exceptions import (
    RefundError,
    PaymentProcessorResponseNotFound,
    MissingProcessorResponseCardInfo,
    MissingTransactionDetailError
)
from oscar.core.loading import get_model
from oscar.apps.payment.exceptions import GatewayError
from ecommerce.extensions.payment.processors import (
    BaseClientSidePaymentProcessor,
    HandledProcessorResponse
)
from ecommerce.core.url_utils import get_ecommerce_url, get_lms_dashboard_url
from ecommerce.extensions.payment.utils import LxmlObjectJsonEncoder

logger = logging.getLogger(__name__)
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

AUTH_CAPTURE_TRANSACTION_TYPE = "authCaptureTransaction"


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
        configuration = self.configuration
        self.merchant_auth_name = configuration['merchant_auth_name']
        self.transaction_key = configuration['transaction_key']
        self.autorizenet_redirect_url = configuration['redirect_url']

    @property
    def cancel_url(self):
        return get_ecommerce_url(self.configuration['cancel_checkout_path'])

    def _get_authorizenet_payment_settings(self, basket):
        """
            return AuthorizeNet_sdk Setting Instance containing required transaction settings to control the
            receipt page urls and buttons. Visit https://developer.authorize.net/api/reference/features/accept_hosted.html
            for more detail.
        """
        course_id = basket.all_lines()[0].product.course_id
        course_id_hash = base64.b64encode(course_id.encode())

        redirect_url = reverse('authorizenet:redirect')
        ecommerce_base_url = get_ecommerce_url()

        return_url = '{}{}?course={}'.format(ecommerce_base_url, redirect_url, course_id_hash)

        # Create Authorizenet Settings object
        payment_button_setting = apicontractsv1.settingType()
        payment_button_setting.settingName = apicontractsv1.settingNameEnum.hostedPaymentButtonOptions
        payment_button_setting.settingValue = json.dumps({'text': 'Pay'})

        payment_return_setting = apicontractsv1.settingType()
        payment_return_setting.settingName = apicontractsv1.settingNameEnum.hostedPaymentReturnOptions
        payment_return_configrations = {
            'url': return_url,
            'urlText': 'Continue',
            'cancelUrl': self.cancel_url,
            'cancelUrlText': 'Cancel'
        }
        payment_return_setting.settingValue = json.dumps(payment_return_configrations)

        settings = apicontractsv1.ArrayOfSetting()
        settings.setting.append(payment_button_setting)
        settings.setting.append(payment_return_setting)
        return settings

    def _get_authorizenet_lineitems(self, basket):
        """
            return AuthorizeNet_sdk lineItem List Instance containing all items data received from basket.
        """
        line_items_list = apicontractsv1.ArrayOfLineItem()
        for line in basket.all_lines():
            line_item = apicontractsv1.lineItemType()
            line_item.itemId = line.product.course_id
            line_item.name = line.product.course_id
            line_item.description = line.product.title
            line_item.quantity = line.quantity
            line_item.unitPrice = line.line_price_incl_tax_incl_discounts / line.quantity
            line_items_list.lineItem.append(line_item)
        return line_items_list

    def get_transaction_detail(self, transaction_id):
        """
            Return complete transaction details using AuthorizeNet transaction id. For more information
            visit https://developer.authorize.net/api/reference/#transaction-reporting-get-transaction-details

            Arguments:
                transaction_id: transaction id received from AuthorizeNet Notification.
            Returns:
                Complete transaction detail
        """
        merchant_auth = apicontractsv1.merchantAuthenticationType()
        merchant_auth.name = self.merchant_auth_name
        merchant_auth.transactionKey = self.transaction_key

        transaction_details_request = apicontractsv1.getTransactionDetailsRequest()
        transaction_details_request.merchantAuthentication = merchant_auth
        transaction_details_request.transId = transaction_id

        transaction_details_controller = getTransactionDetailsController(transaction_details_request)
        transaction_details_controller.execute()

        transaction_details_response = transaction_details_controller.getresponse()
        if transaction_details_response is not None:
            if transaction_details_response.messages.resultCode == apicontractsv1.messageTypeEnum.Ok:
                logger.info('Successfully got Authorizenet transaction details')

                if transaction_details_response.messages is not None:
                    logger.info('Message Code : %s' % transaction_details_response.messages.message[0]['code'].text)
                    logger.info('Message Text : %s' % transaction_details_response.messages.message[0]['text'].text)
            else:
                logger.error(
                    'Unable to get Authorizenet transaction detail using transaction_id [%s].', transaction_id)
                if transaction_details_response.messages is not None:
                    logger.error('Failed to get transaction details.\nCode:%s \nText:%s' % (
                        transaction_details_response.messages.message[0]['code'].text,
                        transaction_details_response.messages.message[0]['text'].text)
                    )
                raise MissingTransactionDetailError
        return transaction_details_response

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=True, **kwargs):
        """
            Create a new AuthorizeNet payment form token.

            Visit following links for more information and detail
            https://developer.authorize.net/api/reference/#accept-suite-get-an-accept-payment-page
            https://developer.authorize.net/api/reference/features/accept_hosted.html (redirection method)

        Arguments:
            basket (Basket): The basket of products being purchased.
            request (Request, optional): A Request object which is used to construct AuthorizeNet's `return_url`.
            use_client_side_checkout (bool, optional): This value is not used.
            **kwargs: Additional parameters; not used by this method.

        Returns:
            dict: AuthorizeNet-specific parameters required to complete a transaction. Must contain a URL
                to which users can be directed in order to approve a newly created payment.

        Raises:
            GatewayError: Indicates a general error or unexpected behavior on the part of AuthorizeNet which prevented
                a payment from being created.
        """

        merchant_auth = apicontractsv1.merchantAuthenticationType()
        merchant_auth.name = self.merchant_auth_name
        merchant_auth.transactionKey = self.transaction_key

        settings = self._get_authorizenet_payment_settings(basket)
        order = apicontractsv1.orderType()
        order.invoiceNumber = basket.order_number

        transaction_request = apicontractsv1.transactionRequestType()
        transaction_request.transactionType = AUTH_CAPTURE_TRANSACTION_TYPE
        transaction_request.amount = unicode(basket.total_incl_tax)
        transaction_request.order = order

        line_items_list = self._get_authorizenet_lineitems(basket)
        payment_page_request = apicontractsv1.getHostedPaymentPageRequest()
        payment_page_request.merchantAuthentication = merchant_auth
        payment_page_request.transactionRequest = transaction_request
        payment_page_request.hostedPaymentSettings = settings
        transaction_request.lineItems = line_items_list

        payment_page_controller = getHostedPaymentPageController(payment_page_request)
        payment_page_controller.execute()

        payment_page_response = payment_page_controller.getresponse()
        authorize_form_token = ""

        if payment_page_response is not None:
            if payment_page_response.messages.resultCode == apicontractsv1.messageTypeEnum.Ok:
                logger.info(
                    "%s [%d].",
                    "Successfully got hosted payment page for basket",
                    basket.id,
                    exc_info=True
                )
                if payment_page_response.messages is not None:
                    logger.info('Message Code : %s' % payment_page_response.messages.message[0]['code'].text)
                    logger.info('Message Text : %s' % payment_page_response.messages.message[0]['text'].text)
                authorize_form_token = str(payment_page_response.token)

            else:
                logger.error('Failed to get AuthorizeNet payment token.')
                if payment_page_response.messages is not None:
                    logger.error(
                        '\nCode:%s \nText:%s' % (
                            payment_page_response.messages.message[0]['code'].text,
                            payment_page_response.messages.message[0]['text'].text
                        )
                    )
                raise GatewayError(payment_page_response.messages.message[0]['text'].text)
        else:
            logger.error(
                "%s [%d].",
                "Failed to create AuthorizeNet payment for basket",
                basket.id,
                exc_info=True
            )
            raise GatewayError('AuthorizeNet payment creation failure: unable to get AuthorizeNet form token')

        parameters = {
            'payment_page_url': self.autorizenet_redirect_url,
            'token': authorize_form_token
        }
        return parameters

    def handle_processor_response(self, transaction_response, basket=None):
        """
            Execute an approved AuthorizeNet transaction. This method will record payment processor
            response for future usage.

            Arguments:
                transaction_response: Transaction details received from authorizeNet after successfull payment
                basket (Basket): Basket being purchased via the payment processor.

            Returns:
                HandledProcessorResponse
        """
        transaction_id = transaction_response.transaction.transId
        transaction_dict = LxmlObjectJsonEncoder().encode(transaction_response)

        self.record_processor_response(transaction_dict, transaction_id=transaction_id, basket=basket)
        logger.info("Successfully executed AuthorizeNet payment [%s] for basket [%d].", transaction_id, basket.id)

        currency = basket.currency
        total = float(transaction_response.transaction.settleAmount)
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
        """
            Refund a AuthorizeNet payment for settled transactions.For more Authorizenet Refund API information,
            visit https://developer.authorize.net/api/reference/#payment-transactions-refund-a-transaction
        """
        try:
            paymnet_response = PaymentProcessorResponse.objects.filter(
                processor_name=self.NAME,
                transaction_id=reference_number
            ).latest('created')
            reference_transaction_details = json.loads(paymnet_response.response)
        except:
            msg = 'AuthorizeNet issue credit error for order [{}]. Unable to get payment reponse and transaction details.'.format(
                order_number)
            logger.exception(msg)
            raise PaymentProcessorResponseNotFound(msg)

        transaction_card_info = reference_transaction_details.get('transaction', {}).get('payment', {}).get('creditCard', {})

        if not transaction_card_info:
            msg = 'AuthorizeNet issue credit error for order [{}]. Unable to get card-information from transaction details.'.format(
                order_number)
            logger.exception(msg)
            raise MissingProcessorResponseCardInfo(msg)

        merchant_auth = apicontractsv1.merchantAuthenticationType()
        merchant_auth.name = self.merchant_auth_name
        merchant_auth.transactionKey = self.transaction_key

        credit_card = apicontractsv1.creditCardType()
        credit_card.cardNumber = transaction_card_info.get('cardNumber', "")[-4:]
        credit_card.expirationDate = transaction_card_info.get('expirationDate', "")

        payment = apicontractsv1.paymentType()
        payment.creditCard = credit_card

        transaction_request = apicontractsv1.transactionRequestType()
        transaction_request.transactionType = "refundTransaction"
        transaction_request.amount = amount

        transaction_request.refTransId = reference_number # set refTransId to transId of a settled transaction
        transaction_request.payment = payment

        create_transaction_request = apicontractsv1.createTransactionRequest()
        create_transaction_request.merchantAuthentication = merchant_auth

        create_transaction_request.transactionRequest = transaction_request
        create_transaction_controller = createTransactionController(create_transaction_request)
        create_transaction_controller.execute()

        response = create_transaction_controller.getresponse()
        if response is not None:
            if response.messages.resultCode == "Ok":
                if hasattr(response.transactionResponse, 'messages') == True:
                    logger.info('Message Code: %s' % response.transactionResponse.messages.message[0].code)
                    logger.info('Description: %s' % response.transactionResponse.messages.message[0].description)

                    refund_transaction_id = response.transactionResponse.transId
                    refund_transaction_dict = LxmlObjectJsonEncoder().encode(response)

                    self.record_processor_response(refund_transaction_dict, transaction_id=refund_transaction_id, basket=basket)
                    return refund_transaction_id
                else:
                    logger.error('AuthorizeNet issue credit request failed.')
                    if hasattr(response.transactionResponse, 'errors') == True:
                        logger.error('Error Code:  %s' % str(response.transactionResponse.errors.error[0].errorCode))
                        logger.error('Error message: %s' % response.transactionResponse.errors.error[0].errorText)
            else:
                logger.error('AuthorizeNet issue credit request failed.')
                if hasattr(response, 'transactionResponse') == True and hasattr(response.transactionResponse, 'errors') == True:
                    logger.error('Error Code: %s' % str(response.transactionResponse.errors.error[0].errorCode))
                    logger.error('Error message: %s' % response.transactionResponse.errors.error[0].errorText)
                else:
                    logger.error('Error Code: %s' % response.messages.message[0]['code'].text)
                    logger.error('Error message: %s' % response.messages.message[0]['text'].text)

        msg = 'An error occurred while attempting to issue a credit (via Authorizenet) for order [{}].'.format(order_number)
        logger.exception(msg)
        raise  RefundError(msg)
