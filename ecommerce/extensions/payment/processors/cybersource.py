""" CyberSource payment processing. """


import base64
import datetime
import json
import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional

import jwt
import jwt.exceptions
import waffle
from CyberSource import (
    AuthReversalRequest,
    CreatePaymentRequest,
    GeneratePublicKeyRequest,
    KeyGenerationApi,
    PaymentsApi,
    Ptsv2paymentsClientReferenceInformation,
    Ptsv2paymentsidreversalsClientReferenceInformation,
    Ptsv2paymentsidreversalsReversalInformation,
    Ptsv2paymentsidreversalsReversalInformationAmountDetails,
    Ptsv2paymentsMerchantDefinedInformation,
    Ptsv2paymentsOrderInformation,
    Ptsv2paymentsOrderInformationAmountDetails,
    Ptsv2paymentsOrderInformationBillTo,
    Ptsv2paymentsOrderInformationInvoiceDetails,
    Ptsv2paymentsOrderInformationLineItems,
    Ptsv2paymentsProcessingInformation,
    Ptsv2paymentsTokenInformation,
    ReversalApi
)
from CyberSource.rest import ApiException
from django.conf import settings
from django.urls import reverse
from jwt.algorithms import RSAAlgorithm
from oscar.apps.payment.exceptions import GatewayError, TransactionDeclined, UserCancelled
from oscar.core.loading import get_class, get_model
from pytz import UTC
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


BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
Order = get_model('order', 'Order')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


def del_none(d):  # pragma: no cover
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
    authorized_pending_review = 'AUTHORIZED_PENDING_REVIEW'


@dataclass
class UnhandledCybersourceResponse:
    decision: Decision
    duplicate_payment: bool
    partial_authorization: bool
    currency: Optional[str]
    total: Optional[Decimal]
    card_number: Optional[str]
    card_type: Optional[str]
    transaction_id: str
    order_id: Optional[str]
    raw_json: dict


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
        if self.site.siteconfiguration.payment_microfrontend_url:
            self.flex_target_origin = self.site.siteconfiguration.payment_microfrontend_url.rstrip('/')
        else:
            self.flex_target_origin = None

        self.connect_timeout = configuration.get('api_connect_timeout', 0.5)
        self.read_timeout = configuration.get('api_read_timeout', 5.0)

        self.cybersource_api_config = {
            'authentication_type': 'http_signature',
            'run_environment': self.flex_run_environment,
            'merchantid': self.merchant_id,
            'merchant_keyid': self.flex_shared_secret_key_id,
            'merchant_secretkey': self.flex_shared_secret_key,
            'enable_log': False,
        }

    @property
    def cancel_page_url(self):
        return get_ecommerce_url(self.configuration['cancel_checkout_path'])

    @property
    def client_side_payment_url(self):
        return self.sop_payment_page_url

    def get_capture_context(self, session):  # pragma: no cover
        # To delete None values in Input Request Json body

        requestObj = GeneratePublicKeyRequest(
            encryption_type='RsaOaep256',
            target_origin=self.flex_target_origin,
        )
        requestObj = del_none(requestObj.__dict__)
        requestObj = json.dumps(requestObj)

        api_instance = KeyGenerationApi(self.cybersource_api_config)
        return_data, _, _ = api_instance.generate_public_key(
            generate_public_key_request=requestObj,
            format='JWT',
            _request_timeout=(self.connect_timeout, self.read_timeout),
        )

        new_capture_context = {'key_id': return_data.key_id}

        capture_contexts = [
            capture_context
            for (capture_context, _)
            in self._unexpired_capture_contexts(session)
        ]
        capture_contexts.insert(0, new_capture_context)
        # Prevent session size explosion by limiting the number of recorded capture contexts
        session['capture_contexts'] = capture_contexts[:20]
        return new_capture_context

    def _unexpired_capture_contexts(self, session):
        """
        Return all unexpired capture contexts in the supplied session.

        Arguments:
            session (Session): the current user session

        Returns: [(capture_context, decoded_capture_context)]
            The list of all still-valid capture contexts, both encoded and decoded
        """
        now = datetime.datetime.now(UTC)
        return [
            (capture_context, decoded_capture_context)
            for (capture_context, decoded_capture_context)
            in (
                (capture_context, jwt.decode(capture_context['key_id'], verify=False))
                for capture_context
                in session.get('capture_contexts', [])
            )
            if not datetime.datetime.fromtimestamp(decoded_capture_context['exp'], tz=UTC) < now
        ]

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

    def normalize_processor_response(self, response: dict) -> UnhandledCybersourceResponse:
        # Raise an exception for payments that were not accepted. Consuming code should be responsible for handling
        # and logging the exception.
        try:
            decision = Decision(response['decision'].upper())
        except ValueError:
            decision = response['decision']

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
            raw_json=self.serialize_order_completion(response),
        )
        return _response

    def serialize_order_completion(self, order_completion_message):
        return serialize_object(order_completion_message)

    def extract_reason_code(self, order_completion_message):
        return order_completion_message.get('reason_code')

    def extract_payment_response_message(self, order_completion_message):
        return order_completion_message.get('message')

    def get_billing_address(self, order_completion_message):

        field = 'req_bill_to_address_line1'
        # Address line 1 is optional if flag is enabled
        line1 = (
            order_completion_message.get(field, '')
            if waffle.switch_is_active('optional_location_fields')
            else order_completion_message[field]
        )
        return BillingAddress(
            first_name=order_completion_message['req_bill_to_forename'],
            last_name=order_completion_message['req_bill_to_surname'],
            line1=line1,

            # Address line 2 is optional
            line2=order_completion_message.get('req_bill_to_address_line2', ''),

            # Oscar uses line4 for city
            line4=order_completion_message['req_bill_to_address_city'],
            # Postal code is optional
            postcode=order_completion_message.get('req_bill_to_address_postal_code', ''),
            # State is optional
            state=order_completion_message.get('req_bill_to_address_state', ''),
            country=Country.objects.get(
                iso_3166_1_a2=order_completion_message['req_bill_to_address_country']))

    def handle_processor_response(self, response: UnhandledCybersourceResponse, basket=None):
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
        # Validate the signature
        if not self.is_signature_valid(response.raw_json):
            raise InvalidSignatureError()

        if response.decision != Decision.accept:
            if response.duplicate_payment:
                # This means user submitted payment request twice within 15 min.
                # We need to check if user first payment notification was handled successfuly and user has an order
                # if user has an order we can raise DuplicateReferenceNumber exception else we need to continue
                # the order creation process. to upgrade user in correct course mode.
                if Order.objects.filter(number=response.order_id).exists():
                    raise DuplicateReferenceNumber

                # If we failed to capture a successful payment, and then the user submits payment again within a 15
                # minute window, then we get a duplicate payment message with no amount attached. We can't create an
                # order in that case.
                if response.total is None:
                    raise DuplicateReferenceNumber

                logger.info(
                    'Received duplicate CyberSource payment notification for basket [%d] which is not associated '
                    'with any existing order. Continuing to validation and order creation processes.',
                    basket.id,
                )
            else:
                if response.decision == Decision.authorized_pending_review:
                    self.reverse_payment_api(response, "Automatic reversal of AUTHORIZED_PENDING_REVIEW", basket)

                raise {
                    Decision.cancel: UserCancelled,
                    Decision.decline: TransactionDeclined,
                    Decision.error: GatewayError,
                    Decision.review: AuthorizationError,
                    Decision.authorized_pending_review: TransactionDeclined,
                }.get(response.decision, InvalidCybersourceDecision(response.decision))

        transaction_id = response.transaction_id
        if transaction_id and response.decision == Decision.accept:
            if Order.objects.filter(number=response.order_id).exists():
                if PaymentProcessorResponse.objects.filter(transaction_id=transaction_id).exists():
                    raise RedundantPaymentNotificationError
                raise ExcessivePaymentForOrderError

        if response.partial_authorization:
            # Raise an exception if the authorized amount differs from the requested amount.
            # Note (CCB): We should never reach this point in production since partial authorization is disabled
            # for our account, and should remain that way until we have a proper solution to allowing users to
            # complete authorization for the entire order
            raise PartialAuthorizationError

        return HandledProcessorResponse(
            transaction_id=response.transaction_id,
            total=response.total,
            currency=response.currency,
            card_number=response.card_number,
            card_type=response.card_type
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
        """
        Verify the payment processor used for the original order responds as expected to the refund request,
        and the response is saved in the database, with error handling.
        """
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

    def record_processor_response(self, response, transaction_id=None, basket=None):
        if isinstance(response, UnhandledCybersourceResponse):
            response = response.raw_json

        return super().record_processor_response(response, transaction_id=transaction_id, basket=basket)


class CybersourceREST(Cybersource):
    """
    A temporary PaymentProcessor dedicated to carefully switching to the Cybersource REST payment api
    """

    NAME = "cybersource-rest"

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
            payment_processor_response = self.authorize_payment_api(
                transient_token_jwt,
                basket,
                request,
                form_data,
            )
            return payment_processor_response, payment_processor_response.id
        except ApiException as e:
            if e.body is None:
                self.record_processor_response({
                    'status': e.status,
                    'reason': e.reason,
                }, transaction_id=None, basket=basket)
                logger.exception('Payment failed')
                # This will display the generic error on the frontend
                raise GatewayError()
            return e, e.headers['v-c-correlation-id']

    def normalize_processor_response(self, response) -> UnhandledCybersourceResponse:
        decision_map = {
            'AUTHORIZED': Decision.accept,
            'PARTIAL_AUTHORIZED': Decision.decline,
            'AUTHORIZED_PENDING_REVIEW': Decision.authorized_pending_review,
            'AUTHORIZED_RISK_DECLINED': Decision.decline,
            'PENDING_AUTHENTICATION': Decision.decline,
            'PENDING_REVIEW': Decision.review,
            'DECLINED': Decision.decline,
            'INVALID_REQUEST': Decision.error,
        }
        response_json = self.serialize_order_completion(response)

        if isinstance(response, ApiException):
            decision = decision_map.get(response_json.get('status'), response_json.get('status'))

            return UnhandledCybersourceResponse(
                decision=decision,
                duplicate_payment=(
                    decision == Decision.error and
                    response_json.get('reason') == 'DUPLICATE_REQUEST'
                ),
                partial_authorization=False,
                currency=None,
                total=None,
                card_number=None,
                card_type=None,
                transaction_id=None,
                order_id=None,
                raw_json=response_json,
            )

        decision = decision_map.get(response.status, response.status)

        currency = None
        total = None
        amount_details = response.order_information and response.order_information.amount_details
        if amount_details:
            currency = amount_details.currency
            total = (
                amount_details.total_amount or
                amount_details.authorized_amount
            )
        if total:
            total = Decimal(total)

        card = response.payment_information and response.payment_information.tokenized_card
        card_type = card and CYBERSOURCE_CARD_TYPE_MAP.get(card.type)

        return UnhandledCybersourceResponse(
            decision=decision,
            duplicate_payment=(
                decision == Decision.error and
                response.reason == 'DUPLICATE_REQUEST'
            ),
            partial_authorization=response.status == 'PARTIAL_AUTHORIZED',
            currency=currency,
            total=total,
            card_number=response.decoded_payment_token['data']['number'],
            card_type=card_type,
            transaction_id=response.id,
            order_id=response.client_reference_information.code,
            raw_json=response_json,
        )

    def serialize_order_completion(self, order_completion_message):
        if isinstance(order_completion_message, ApiException):
            try:
                return json.loads(order_completion_message.body)
            except:  # pylint: disable=bare-except
                return {}

        return order_completion_message.to_dict()

    def extract_reason_code(self, order_completion_message):
        if isinstance(order_completion_message, ApiException):
            return self.serialize_order_completion(order_completion_message).get('reason')
        return order_completion_message.error_information and order_completion_message.error_information.reason

    def extract_payment_response_message(self, order_completion_message):
        if isinstance(order_completion_message, ApiException):
            return self.serialize_order_completion(order_completion_message).get('message')

        return order_completion_message.error_information and order_completion_message.error_information.message

    def is_signature_valid(self, response):
        """Returns a boolean indicating if the response's signature (indicating potential tampering) is valid."""
        # There is no need to validate the payment processor response, because
        # it is coming in response to an API call we initiated
        return True

    def reverse_payment_api(self, payment_processor_response: UnhandledCybersourceResponse, reason: str, basket=None):

        clientReferenceInformation = Ptsv2paymentsidreversalsClientReferenceInformation(
            code=payment_processor_response.order_id
        )

        reversalInformationAmountDetails = Ptsv2paymentsidreversalsReversalInformationAmountDetails(
            total_amount=str(payment_processor_response.total)
        )

        reversalInformation = Ptsv2paymentsidreversalsReversalInformation(
            amount_details=reversalInformationAmountDetails.__dict__,
            reason=reason,
        )

        requestObj = AuthReversalRequest(
            client_reference_information=clientReferenceInformation.__dict__,
            reversal_information=reversalInformation.__dict__
        )

        requestObj = del_none(requestObj.__dict__)

        # HACK: log the processor request into the processor response model for analyzing declines
        self.record_processor_response(requestObj, transaction_id='[REVERSAL REQUEST]', basket=basket)

        api_instance = ReversalApi(self.cybersource_api_config)

        try:
            reversal_response, _, _ = api_instance.auth_reversal(
                payment_processor_response.transaction_id,
                json.dumps(requestObj),
                _request_timeout=(self.connect_timeout, self.read_timeout)
            )
        except ApiException as e:
            reversal_response = e

        if isinstance(reversal_response, ApiException):
            reversal_transaction_id = None
        else:
            reversal_transaction_id = reversal_response.id

        self.record_processor_response(
            self.serialize_order_completion(reversal_response),
            transaction_id=reversal_transaction_id,
            basket=basket,
        )
        return reversal_response

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
            merchant_defined_information=merchantDefinedInformation
        )

        requestObj = del_none(requestObj.__dict__)

        # HACK: log the processor request into the processor response model for analyzing declines
        self.record_processor_response(requestObj, transaction_id='[REQUEST]', basket=basket)

        api_instance = PaymentsApi(self.cybersource_api_config)
        payment_processor_response, _, _ = api_instance.create_payment(
            json.dumps(requestObj),
            _request_timeout=(self.connect_timeout, self.read_timeout)
        )

        # Add the billing address to the response so it's available for the rest of the order completion process
        payment_processor_response.billing_address = BillingAddress(
            first_name=form_data['first_name'],
            last_name=form_data['last_name'],
            line1=form_data['address_line1'],
            line2=form_data['address_line2'],
            line4=form_data['city'],
            postcode=form_data['postal_code'],
            state=form_data['state'],
            country=Country.objects.get(iso_3166_1_a2=form_data['country'])
        )
        decoded_payment_token = None
        for _, decoded_capture_context in self._unexpired_capture_contexts(request.session):
            jwk = RSAAlgorithm.from_jwk(json.dumps(decoded_capture_context['flx']['jwk']))
            # We don't know which capture context was used for this payment token, so just try all unexpired ones
            try:
                decoded_payment_token = jwt.decode(transient_token_jwt, key=jwk, algorithms=['RS256'])
            except jwt.exceptions.InvalidSignatureError:
                continue
            else:
                break

        if decoded_payment_token is None:
            # Couldn't find a capture context that is valid for this payment token
            raise InvalidSignatureError()

        payment_processor_response.decoded_payment_token = decoded_payment_token
        return payment_processor_response

    def get_billing_address(self, order_completion_message):
        return order_completion_message.billing_address
