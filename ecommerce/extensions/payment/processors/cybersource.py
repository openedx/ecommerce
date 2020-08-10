""" CyberSource payment processing. """


import base64
from dataclasses import dataclass
import datetime
from enum import Enum
import json
import logging
import uuid
from decimal import Decimal

from CyberSource import (
    GeneratePublicKeyRequest, KeyGenerationApi, Ptsv2paymentsClientReferenceInformation, Ptsv2paymentsProcessingInformation, Ptsv2paymentsTokenInformation,
    Ptsv2paymentsOrderInformationAmountDetails, Ptsv2paymentsOrderInformationBillTo, Ptsv2paymentsOrderInformationLineItems,
    Ptsv2paymentsOrderInformationInvoiceDetails, Ptsv2paymentsOrderInformation, PaymentsApi, Ptsv2paymentsMerchantDefinedInformation,
    CreatePaymentRequest
)
from CyberSource.rest import ApiException
from django.conf import settings
from django.urls import reverse
import jwt
from jwt.algorithms import RSAAlgorithm
from oscar.apps.payment.exceptions import GatewayError, TransactionDeclined, UserCancelled
from oscar.core.loading import get_class, get_model
from zeep import Client
from zeep.helpers import serialize_object
from zeep.wsse import UsernameToken

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.constants import APPLE_PAY_CYBERSOURCE_CARD_TYPE_MAP, CYBERSOURCE_CARD_TYPE_MAP
from ecommerce.extensions.payment.exceptions import (
    AuthorizationError,
    DuplicateReferenceNumber,
    ExcessivePaymentForOrderError,
    InvalidCybersourceDecision,
    InvalidSignatureError,
    PartialAuthorizationError,
    PCIViolation,
    ProcessorMisconfiguredError,
    RedundantPaymentNotificationError
)
from ecommerce.extensions.payment.helpers import sign
from ecommerce.extensions.payment.processors import (
    ApplePayMixin,
    BaseClientSidePaymentProcessor,
    HandledProcessorResponse
)
from ecommerce.extensions.payment.utils import clean_field_value, get_basket_program_uuid

logger = logging.getLogger(__name__)

Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')



def del_none(d):
    for key, value in list(d.items()):
        if value is None:
            del d[key]
        elif isinstance(value, dict):
            del_none(value)
    return d


class Decision(Enum):
    accept = 'ACCEPT'
    cancel = 'CANCEL'
    decline = 'DECLINE'
    error = 'ERROR'
    review = 'REVIEW'
    invalid = 'invalid'  # Used when the Cybersource decision doesn't match a known decision type


@dataclass
class UnhandledCybersourceResponse:
    decision: Decision
    duplicate_payment: bool
    partial_authorization: bool
    currency: str
    total: Decimal
    card_number: str
    card_type: str
    transaction_id: str
    order_id: str


class Cybersource(ApplePayMixin, BaseClientSidePaymentProcessor):
    """
    CyberSource Secure Acceptance Web/Mobile (February 2015)

    For reference, see
    http://apps.cybersource.com/library/documentation/dev_guides/Secure_Acceptance_WM/Secure_Acceptance_WM.pdf.
    """

    NAME = 'cybersource'
    PCI_FIELDS = ('card_cvn', 'card_expiry_date', 'card_number', 'card_type',)

    def __init__(self, site):
        """
        Constructs a new instance of the CyberSource processor.

        Raises:
            KeyError: If no settings configured for this payment processor
            AttributeError: If LANGUAGE_CODE setting is not set.
        """

        super(Cybersource, self).__init__(site)
        configuration = self.configuration
        self.soap_api_url = configuration['soap_api_url']
        self.merchant_id = configuration['merchant_id']
        self.transaction_key = configuration['transaction_key']
        self.send_level_2_3_details = configuration.get('send_level_2_3_details', True)
        self.language_code = settings.LANGUAGE_CODE

        # Secure Acceptance parameters
        # NOTE: Silent Order POST is the preferred method of checkout as it allows us to completely control
        # the checkout UX. Secure Acceptance, on the other hand, redirects the purchaser to a page controlled
        # by CyberSource.
        self.profile_id = configuration.get('profile_id')
        self.access_key = configuration.get('access_key')
        self.secret_key = configuration.get('secret_key')
        self.payment_page_url = configuration.get('payment_page_url')

        # Silent Order POST parameters
        self.sop_profile_id = configuration.get('sop_profile_id')
        self.sop_access_key = configuration.get('sop_access_key')
        self.sop_secret_key = configuration.get('sop_secret_key')
        self.sop_payment_page_url = configuration.get('sop_payment_page_url')

        sa_configured = all((self.access_key, self.payment_page_url, self.profile_id, self.secret_key))
        sop_configured = all([self.sop_access_key, self.sop_payment_page_url, self.sop_profile_id, self.sop_secret_key])
        assert sop_configured or sa_configured, \
            'CyberSource processor must be configured for Silent Order POST and/or Secure Acceptance'

        # Apple Pay configuration
        self.apple_pay_enabled = self.site.siteconfiguration.enable_apple_pay
        self.apple_pay_merchant_identifier = configuration.get('apple_pay_merchant_identifier', '')
        self.apple_pay_merchant_id_certificate_path = configuration.get('apple_pay_merchant_id_certificate_path', '')
        self.apple_pay_country_code = configuration.get('apple_pay_country_code', '')

        # Flex Microform configuration
        self.flex_run_environment = configuration.get('flex_run_environment', 'cybersource.environment.SANDBOX')
        self.flex_shared_secret_key_id = configuration.get('flex_shared_secret_key_id')
        self.flex_shared_secret_key = configuration.get('flex_shared_secret_key')
        self.flex_target_origin = self.site.siteconfiguration.payment_microfrontend_url
        self.cybersource_api_config = {
            'authentication_type': 'http_signature',
            'run_environment': self.flex_run_environment,
            'merchantid': self.merchant_id,
            'merchant_keyid': self.flex_shared_secret_key_id,
            'merchant_secretkey': self.flex_shared_secret_key,
        }

    @property
    def cancel_page_url(self):
        return get_ecommerce_url(self.configuration['cancel_checkout_path'])

    @property
    def client_side_payment_url(self):
        return self.sop_payment_page_url
    
    def get_capture_context(self):
        # To delete None values in Input Request Json body

        requestObj = GeneratePublicKeyRequest(
            encryption_type='RsaOaep256',
            target_origin=self.flex_target_origin,
        )
        requestObj = del_none(requestObj.__dict__)
        requestObj = json.dumps(requestObj)

        api_instance = KeyGenerationApi(self.cybersource_api_config)
        return_data, status, body = api_instance.generate_public_key(requestObj, format='JWT')

        return {'key_id': return_data.key_id}

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """
        Generate a dictionary of signed parameters CyberSource requires to complete a transaction.

        Arguments:
            use_client_side_checkout:
            basket (Basket): The basket of products being purchased.
            request (Request, optional): A Request object which could be used to construct an absolute URL; not
                used by this method.
            use_client_side_checkout (bool, optional): Indicates if the Silent Order POST profile should be used.
            **kwargs: Additional parameters.

        Keyword Arguments:
            extra_parameters (dict): Additional signed parameters that should be included in the signature
                and returned dict. Note that these parameters will override any default values.

        Returns:
            dict: CyberSource-specific parameters required to complete a transaction, including a signature.
        """
        sop_config_values = (self.sop_access_key, self.sop_payment_page_url, self.sop_profile_id, self.sop_secret_key,)
        if use_client_side_checkout and not all(sop_config_values):
            raise ProcessorMisconfiguredError(
                'CyberSource Silent Order POST cannot be used unless a profile ID, access key, '
                'secret key, and payment page URL are ALL configured in settings.'
            )

        parameters = self._generate_parameters(basket, use_client_side_checkout, **kwargs)

        # Sign all fields
        parameters['signed_field_names'] = ','.join(sorted(parameters.keys()))
        parameters['signature'] = self._generate_signature(parameters, use_client_side_checkout)

        payment_page_url = self.sop_payment_page_url if use_client_side_checkout else self.payment_page_url
        parameters['payment_page_url'] = payment_page_url

        return parameters

    def _generate_parameters(self, basket, use_sop_profile, **kwargs):
        """ Generates the parameters dict.

        A signature is NOT included in the parameters.

         Arguments:
            basket (Basket): Basket from which the pricing and item details are pulled.
            use_sop_profile (bool, optional): Indicates if the Silent Order POST profile should be used.
            **kwargs: Additional parameters to add to the generated dict.

         Returns:
             dict: Dictionary containing the payment parameters that should be sent to CyberSource.
        """
        site = basket.site

        access_key = self.access_key
        profile_id = self.profile_id

        if use_sop_profile:
            access_key = self.sop_access_key
            profile_id = self.sop_profile_id

        parameters = {
            'access_key': access_key,
            'profile_id': profile_id,
            'transaction_uuid': uuid.uuid4().hex,
            'signed_field_names': '',
            'unsigned_field_names': '',
            'signed_date_time': datetime.datetime.utcnow().strftime(ISO_8601_FORMAT),
            'locale': self.language_code,
            'transaction_type': 'sale',
            'reference_number': basket.order_number,
            'amount': str(basket.total_incl_tax),
            'currency': basket.currency,
            'override_custom_receipt_page': get_receipt_page_url(
                site_configuration=site.siteconfiguration,
                order_number=basket.order_number,
                override_url=site.siteconfiguration.build_ecommerce_url(
                    reverse('cybersource:redirect')
                ),
                disable_back_button=True,
            ),
            'override_custom_cancel_page': self.cancel_page_url,
        }
        extra_data = []
        # Level 2/3 details
        if self.send_level_2_3_details:
            parameters['amex_data_taa1'] = site.name
            parameters['purchasing_level'] = '3'
            parameters['line_item_count'] = basket.all_lines().count()
            # Note (CCB): This field (purchase order) is required for Visa;
            # but, is not actually used by us/exposed on the order form.
            parameters['user_po'] = 'BLANK'

            # Add a parameter specifying the basket's program, None if not present.
            # This program UUID will *always* be in the merchant_defined_data1, if exists.
            program_uuid = get_basket_program_uuid(basket)
            if program_uuid:
                extra_data.append("program,{program_uuid}".format(program_uuid=program_uuid))
            else:
                extra_data.append(None)

            for index, line in enumerate(basket.all_lines()):
                parameters['item_{}_code'.format(index)] = line.product.get_product_class().slug
                parameters['item_{}_discount_amount '.format(index)] = str(line.discount_value)
                # Note (CCB): This indicates that the total_amount field below includes tax.
                parameters['item_{}_gross_net_indicator'.format(index)] = 'Y'
                parameters['item_{}_name'.format(index)] = clean_field_value(line.product.title)
                parameters['item_{}_quantity'.format(index)] = line.quantity
                parameters['item_{}_sku'.format(index)] = line.stockrecord.partner_sku
                parameters['item_{}_tax_amount'.format(index)] = str(line.line_tax)
                parameters['item_{}_tax_rate'.format(index)] = '0'
                parameters['item_{}_total_amount '.format(index)] = str(line.line_price_incl_tax_incl_discounts)
                # Note (CCB): Course seat is not a unit of measure. Use item (ITM).
                parameters['item_{}_unit_of_measure'.format(index)] = 'ITM'
                parameters['item_{}_unit_price'.format(index)] = str(line.unit_price_incl_tax)

                # For each basket line having a course product, add course_id and course type
                # as an extra CSV-formatted parameter sent to Cybersource.
                # These extra course parameters will be in parameters merchant_defined_data2+.
                line_course = line.product.course
                if line_course:
                    extra_data.append("course,{course_id},{course_type}".format(
                        course_id=line_course.id if line_course else None,
                        course_type=line_course.type if line_course else None
                    ))

        # Only send consumer_id for hosted payment page
        if not use_sop_profile:
            parameters['consumer_id'] = basket.owner.username

        # Add the extra parameters
        parameters.update(kwargs.get('extra_parameters', {}))

        # Mitigate PCI compliance issues
        signed_field_names = list(parameters.keys())
        if any(pci_field in signed_field_names for pci_field in self.PCI_FIELDS):
            raise PCIViolation('One or more PCI-related fields is contained in the payment parameters. '
                               'This service is NOT PCI-compliant! Deactivate this service immediately!')

        if extra_data:
            # CyberSource allows us to send additional data in merchant_defined_data# fields.
            for num, item in enumerate(extra_data, start=1):
                if item:
                    key = u"merchant_defined_data{num}".format(num=num)
                    parameters[key] = item

        return parameters

    def _normalize_processor_response(self, response):
        # Validate the signature
        if not self.is_signature_valid(response):
            raise InvalidSignatureError

        # Raise an exception for payments that were not accepted. Consuming code should be responsible for handling
        # and logging the exception.
        try:
            decision = Decision(response['decision'].upper())
        except ValueError:
            decision = Decision.invalid

        _response = UnhandledCybersourceResponse(
            decision=decision,
            duplicate_payment=(
                decision == Decision.error and int(response['reason_code']) == 104
            ),
            partial_authorization=(
                'auth_amount' in response and
                response['auth_amount'] and
                response['auth_amount'] != response['req_amount']
            ),
            currency=response['req_currency'],
            total=Decimal(response['req_amount']),
            card_number=response['req_card_number'],
            card_type=CYBERSOURCE_CARD_TYPE_MAP.get(response['req_card_type']),
            transaction_id=response.get('transaction_id', ''),   # Error Notifications do not include a transaction id.
            order_id=response['req_reference_number'],
        )
        return _response

    def handle_processor_response(self, response, basket=None):
        """
        Handle a response (i.e., "merchant notification") from CyberSource.

        Arguments:
            response (dict): Dictionary of parameters received from the payment processor.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            AuthorizationError: Authorization was declined.
            UserCancelled: Indicates the user cancelled payment.
            TransactionDeclined: Indicates the payment was declined by the processor.
            GatewayError: Indicates a general error on the part of the processor.
            InvalidCyberSourceDecision: Indicates an unknown decision value.
                Known values are ACCEPT, CANCEL, DECLINE, ERROR, REVIEW.
            PartialAuthorizationError: Indicates only a portion of the requested amount was authorized.

        Returns:
            HandledProcessorResponse
        """
        _response = self._normalize_processor_response(response)

        if _response.decision != Decision.accept:
            if _response.duplicate_payment:
                # This means user submitted payment request twice within 15 min.
                # We need to check if user first payment notification was handled successfuly and user has an order
                # if user has an order we can raise DuplicateReferenceNumber exception else we need to continue
                # the order creation process. to upgrade user in correct course mode.
                if Order.objects.filter(number=_response.order_id).exists():
                    raise DuplicateReferenceNumber
                logger.info(
                    'Received duplicate CyberSource payment notification for basket [%d] which is not associated '
                    'with any existing order. Continuing to validation and order creation processes.',
                    basket.id,
                )
            else:
                raise {
                    Decision.cancel: UserCancelled,
                    Decision.decline: TransactionDeclined,
                    Decision.error: GatewayError,
                    Decision.review: AuthorizationError,
                }.get(_response.decision, InvalidCybersourceDecision)

        transaction_id = _response.transaction_id
        if transaction_id and _response.decision == Decision.accept:
            if Order.objects.filter(number=_response.order_id).exists():
                if PaymentProcessorResponse.objects.filter(transaction_id=transaction_id).exists():
                    raise RedundantPaymentNotificationError
                raise ExcessivePaymentForOrderError

        if _response.partial_authorization:
            # Raise an exception if the authorized amount differs from the requested amount.
            # Note (CCB): We should never reach this point in production since partial authorization is disabled
            # for our account, and should remain that way until we have a proper solution to allowing users to
            # complete authorization for the entire order
            raise PartialAuthorizationError

        return HandledProcessorResponse(
            transaction_id=_response.transaction_id,
            total=_response.total,
            currency=_response.currency,
            card_number=_response.card_number,
            card_type=_response.card_type
        )

    def _generate_signature(self, parameters, use_sop_profile):
        """
        Sign the contents of the provided transaction parameters dictionary.

        This allows CyberSource to verify that the transaction parameters have not been tampered with
        during transit. The parameters dictionary should contain a key 'signed_field_names' which CyberSource
        uses to validate the signature. The message to be signed must contain parameter keys and values ordered
        in the same way they appear in 'signed_field_names'.

        We also use this signature to verify that the signature we get back from Cybersource is valid for
        the parameters that they are giving to us.

        Arguments:
            parameters (dict): A dictionary of transaction parameters.
            use_sop_profile (bool): Indicates if the Silent Order POST profile should be used.

        Returns:
            unicode: the signature for the given parameters
        """
        order_number = None
        basket_id = None

        if 'reference_number' in parameters:
            order_number = parameters['reference_number']
        elif 'req_reference_number' in parameters:
            order_number = parameters['req_reference_number']

        if order_number:
            basket_id = str(OrderNumberGenerator().basket_id(order_number))

        logger.info(
            'Signing CyberSource payment data for basket [%s], to become order [%s].',
            basket_id,
            order_number
        )

        keys = parameters['signed_field_names'].split(',')
        secret_key = self.sop_secret_key if use_sop_profile else self.secret_key

        # Generate a comma-separated list of keys and values to be signed. CyberSource refers to this
        # as a 'Version 1' signature in their documentation.
        message = ','.join(['{key}={value}'.format(key=key, value=parameters.get(key)) for key in keys])

        return sign(message, secret_key)

    def is_signature_valid(self, response):
        """Returns a boolean indicating if the response's signature (indicating potential tampering) is valid."""
        req_profile_id = response.get('req_profile_id')
        if not req_profile_id:
            return False

        use_sop_profile = req_profile_id == self.sop_profile_id
        return response and (self._generate_signature(response, use_sop_profile) == response.get('signature'))

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        try:
            client = Client(self.soap_api_url, wsse=UsernameToken(self.merchant_id, self.transaction_key))

            credit_service = {
                'captureRequestID': reference_number,
                'run': 'true',
            }
            purchase_totals = {
                'currency': currency,
                'grandTotalAmount': str(amount),
            }

            response = client.service.runTransaction(
                merchantID=self.merchant_id,
                merchantReferenceCode=order_number,
                orderRequestToken=reference_number,
                ccCreditService=credit_service,
                purchaseTotals=purchase_totals
            )

            request_id = response.requestID
            ppr = self.record_processor_response(serialize_object(response), transaction_id=request_id,
                                                 basket=basket)
        except:
            msg = 'An error occurred while attempting to issue a credit (via CyberSource) for order [{}].'.format(
                order_number)
            logger.exception(msg)
            raise GatewayError(msg)

        if response.decision == 'ACCEPT':
            return request_id
        raise GatewayError(
            'Failed to issue CyberSource credit for order [{order_number}]. '
            'Complete response has been recorded in entry [{response_id}]'.format(
                order_number=order_number, response_id=ppr.id))

    def request_apple_pay_authorization(self, basket, billing_address, payment_token):
        """
        Authorizes an Apple Pay payment.

        For details on the process, see the CyberSource Simple Order API documentation at
        https://www.cybersource.com/developers/integration_methods/apple_pay/.

        Args:
            basket (Basket)
            billing_address (BillingAddress)
            payment_token (dict)

        Returns:
            HandledProcessorResponse

        Raises:
            GatewayError
        """
        try:
            client = Client(self.soap_api_url, wsse=UsernameToken(self.merchant_id, self.transaction_key))
            card_type = APPLE_PAY_CYBERSOURCE_CARD_TYPE_MAP[payment_token['paymentMethod']['network'].lower()]
            bill_to = {
                'firstName': billing_address.first_name,
                'lastName': billing_address.last_name,
                'street1': billing_address.line1,
                'street2': billing_address.line2,
                'city': billing_address.line4,
                'state': billing_address.state,
                'postalCode': billing_address.postcode,
                'country': billing_address.country.iso_3166_1_a2,
                'email': basket.owner.email,
            }
            purchase_totals = {
                'currency': basket.currency,
                'grandTotalAmount': str(basket.total_incl_tax),
            }
            encrypted_payment = {
                'descriptor': 'RklEPUNPTU1PTi5BUFBMRS5JTkFQUC5QQVlNRU5U',
                'data': base64.b64encode(json.dumps(payment_token['paymentData']).encode('utf-8')),
                'encoding': 'Base64',
            }
            card = {
                'cardType': card_type,
            }
            auth_service = {
                'run': 'true',
            }
            capture_service = {
                'run': 'true',
            }
            # Enable Export Compliance for SDN validation, amongst other checks.
            # See https://www.cybersource.com/products/fraud_management/export_compliance/
            export_service = {
                'run': 'true',
            }
            item = [{
                'id': index,
                'productCode': line.product.get_product_class().slug,
                'productName': clean_field_value(line.product.title),
                'quantity': line.quantity,
                'productSKU': line.stockrecord.partner_sku,
                'taxAmount': str(line.line_tax),
                'unitPrice': str(line.unit_price_incl_tax),
            } for index, line in enumerate(basket.all_lines())]

            response = client.service.runTransaction(
                merchantID=self.merchant_id,
                merchantReferenceCode=basket.order_number,
                billTo=bill_to,
                purchaseTotals=purchase_totals,
                encryptedPayment=encrypted_payment,
                card=card,
                ccAuthService=auth_service,
                ccCaptureService=capture_service,
                exportService=export_service,
                paymentSolution='001',
                item=item,
            )

        except:
            msg = 'An error occurred while authorizing an Apple Pay (via CyberSource) for basket [{}]'.format(basket.id)
            logger.exception(msg)
            raise GatewayError(msg)

        request_id = response.requestID
        ppr = self.record_processor_response(serialize_object(response), transaction_id=request_id, basket=basket)

        if response.decision == 'ACCEPT':
            currency = basket.currency
            total = basket.total_incl_tax
            transaction_id = request_id

            return HandledProcessorResponse(
                transaction_id=transaction_id,
                total=total,
                currency=currency,
                card_number='Apple Pay',
                card_type=CYBERSOURCE_CARD_TYPE_MAP.get(card_type)
            )
        msg = ('CyberSource rejected an Apple Pay authorization request for basket [{basket_id}]. '
               'Complete response has been recorded in entry [{response_id}]')
        msg = msg.format(basket_id=basket.id, response_id=ppr.id)
        logger.warning(msg)
        raise GatewayError(msg)


class CybersourceREST(Cybersource):
    """
    A temporary PaymentProcessor dedicated to carefully switching to the Cybersource REST payment api
    """

    def __init__(self, site, transient_token_jwt, capture_context):
        super(CybersourceREST, self).__init__(site)
        self.transient_token_jwt = transient_token_jwt
        self.capture_context = capture_context

    def initiate_payment(self, basket, request, form_data):
        """
        Initiate payment using the Cybersource REST payment api.

        Returns:
            (payment_processor_response, transaction_id)

        Raises:
            GatewayError: when the REST api call fails
        """
        transient_token_jwt = request.POST['payment_token']

        try:
            payment_processor_response, _, _ = self.authorize_payment_api(transient_token_jwt, basket, request, form_data)
            transaction_id = payment_processor_response.processor_information.transaction_id
            return payment_processor_response, transaction_id
        except ApiException as e:
            self.record_processor_response({
                'status': e.status,
                'reason': e.reason,
                'body': e.body,
                'headers': dict(e.headers),
            }, transaction_id=e.headers['v-c-correlation-id'], basket=basket)
            logger.exception('Payment failed')
            # This will display the generic error on the frontend
            raise GatewayError()

    def _normalize_processor_response(self, response):
        decoded_capture_context = jwt.decode(self.capture_context['key_id'], verify=False)
        jwk = RSAAlgorithm.from_jwk(json.dumps(decoded_capture_context['flx']['jwk']))
        decoded_payment_token = jwt.decode(self.transient_token_jwt, key=jwk, algorithms=['RS256'])

        decision = {
            'AUTHORIZED': Decision.accept,
            'PARTIAL_AUTHORIZED': Decision.decline,
            'AUTHORIZED_PENDING_REVIEW': Decision.review,
            'AUTHORIZED_RISK_DECLINED': Decision.decline,
            'PENDING_AUTHENTICATION': Decision.decline,
            'PENDING_REVIEW': Decision.review,
            'DECLINED': Decision.decline,
            'INVALID_REQUEST': Decision.error,
        }.get(response.status, Decision.invalid)

        _response = UnhandledCybersourceResponse(
            decision=decision,
            duplicate_payment=(
                decision == Decision.error and
                response.reason == 'DUPLICATE_REQUEST'
            ),
            partial_authorization=(
                response.amount_details.authorized_amount and
                response.amount_details.authorized_amount != response.amount_details.total_amount
            ),
            currency=response.order_information.amount_details.currency,
            total=Decimal(response.order_information.amount_details.total_amount),
            card_number=decoded_payment_token['data']['number'],
            card_type=CYBERSOURCE_CARD_TYPE_MAP.get(response.payment_information.tokenized_card.type),
            transaction_id=response.processor_information.transaction_id,
            order_id=response.client_reference_information.code,
        )
        return _response

    def authorize_payment_api(self, transient_token_jwt, basket, request, form_data):
        clientReferenceInformation = Ptsv2paymentsClientReferenceInformation(
            code=basket.order_number,
        )
        processingInformation = Ptsv2paymentsProcessingInformation(
            capture=True,
            purchase_level="3",
        )
        tokenInformation = Ptsv2paymentsTokenInformation(
            transient_token_jwt=transient_token_jwt,
        )
        orderInformationAmountDetails = Ptsv2paymentsOrderInformationAmountDetails(
            total_amount=str(basket.total_incl_tax),
            currency=basket.currency,
        )

        orderInformationBillTo = Ptsv2paymentsOrderInformationBillTo(
            first_name=form_data['first_name'],
            last_name=form_data['last_name'],
            address1=form_data['address_line1'],
            address2=form_data['address_line2'],
            locality=form_data['city'],
            administrative_area=form_data['state'],
            postal_code=form_data['postal_code'],
            country=form_data['country'],
            email=request.user.email,
        )

        merchantDefinedInformation = []
        program_uuid = get_basket_program_uuid(basket)
        if program_uuid:
            programInfo = Ptsv2paymentsMerchantDefinedInformation(
                key="1",
                value="program,{program_uuid}".format(program_uuid=program_uuid)
            )
            merchantDefinedInformation.append(programInfo.__dict__)

        merchantDataIndex = 2
        orderInformationLineItems = []
        for line in basket.all_lines():
            orderInformationLineItem = Ptsv2paymentsOrderInformationLineItems(
                product_name=clean_field_value(line.product.title),
                product_code=line.product.get_product_class().slug,
                product_sku=line.stockrecord.partner_sku,
                quantity=line.quantity,
                unit_price=str(line.unit_price_incl_tax),
                total_amount=str(line.line_price_incl_tax_incl_discounts),
                unit_of_measure='ITM',
                discount_amount=str(line.discount_value),
                discount_applied=True,
                amount_includes_tax=True,
                tax_amount=str(line.line_tax),
                tax_rate='0',
            )
            orderInformationLineItems.append(orderInformationLineItem.__dict__)
            line_course = line.product.course
            if line_course:
                courseInfo = Ptsv2paymentsMerchantDefinedInformation(
                    key=str(merchantDataIndex),
                    value="course,{course_id},{course_type}".format(
                        course_id=line_course.id if line_course else None,
                        course_type=line_course.type if line_course else None
                    )
                )
                merchantDefinedInformation.append(courseInfo.__dict__)
                merchantDataIndex += 1

        orderInformationInvoiceDetails = Ptsv2paymentsOrderInformationInvoiceDetails(
            purchase_order_number='BLANK'
        )

        orderInformation = Ptsv2paymentsOrderInformation(
            amount_details=orderInformationAmountDetails.__dict__,
            bill_to=orderInformationBillTo.__dict__,
            line_items=orderInformationLineItems,
            invoice_details=orderInformationInvoiceDetails.__dict__
        )

        requestObj = CreatePaymentRequest(
            client_reference_information=clientReferenceInformation.__dict__,
            processing_information=processingInformation.__dict__,
            token_information=tokenInformation.__dict__,
            order_information=orderInformation.__dict__,
            merchant_defined_information = merchantDefinedInformation
        )

        requestObj = del_none(requestObj.__dict__)
        requestObj = json.dumps(requestObj)

        api_instance = PaymentsApi(self.cybersource_api_config)
        return api_instance.create_payment(requestObj)
