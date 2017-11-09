""" PayPal payment processing. """
from __future__ import unicode_literals

import logging
import uuid
from decimal import Decimal
from urlparse import urljoin

import re
import waffle
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.functional import cached_property
from django.utils.translation import get_language
from oscar.apps.payment.exceptions import GatewayError

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.payment.alipay_sdk.api import Api
from ecommerce.extensions.payment.constants import PAYPAL_LOCALES
from ecommerce.extensions.payment.models import AlipayProcessorConfiguration, AlipayWebProfile
from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse
from ecommerce.extensions.payment.utils import middle_truncate

from ecommerce.extensions.payment.alipay_sdk.api import AliPay
from ecommerce.extensions.payment import alipay_sdk

import uuid

logger = logging.getLogger(__name__)


class Alipay(BasePaymentProcessor):
    NAME = 'alipay'
    DEFAULT_PROFILE_NAME = 'default'

    def __init__(self, site):
        """
        Constructs a new instance of the PayPal processor.

        Raises:
            KeyError: If a required setting is not configured for this payment processor
        """
        super(Alipay, self).__init__(site)

        # Number of times payment execution is retried after failure.
        self.retry_attempts = AlipayProcessorConfiguration.get_solo().retry_attempts

    @cached_property
    def alipay_api(self):
        """
        Returns Alipay API instance with appropriate configuration
        Returns: Alipay API instance
        """
        return AliPay({
            'mode': self.configuration['mode'],
            'app_id': self.configuration['app_id'],
            'private_key': self.configuration['private_key'],
            'alipay_public_key': self.configuration['alipay_public_key'],
            'sign_type': self.configuration['sign_type'],
            'charset': self.configuration['charset'],
        })

    @property
    def cancel_url(self):
        return get_ecommerce_url(self.configuration['cancel_checkout_path'])

    @property
    def error_url(self):
        return get_ecommerce_url(self.configuration['error_path'])

    def resolve_alipay_locale(self, language_code):
        default_alipay_locale = PAYPAL_LOCALES.get(re.split(r'[_-]', get_language())[0].lower())
        if not language_code:
            return default_alipay_locale
        else:
            return PAYPAL_LOCALES.get(re.split(r'[_-]', language_code)[0].lower(), default_alipay_locale)

    def create_temporary_web_profile(self, locale_code):
        """
        Generates a temporary Alipay WebProfile that carries the locale setting for a Alipay Payment
        and returns the id of the WebProfile
        """
        try:
            web_profile = alipay_sdk.WebProfile({
                "name": str(uuid.uuid1()),  # Generate a unique identifier
                "presentation": {
                    "locale_code": locale_code
                },
                "temporary": True  # Persists for 3 hours
            }, api=self.alipay_api)

            if web_profile.create():
                msg = "Web Profile[%s] for locale %s created successfully" % (
                    web_profile.id,
                    web_profile.presentation.locale_code
                )
                logger.info(msg)
                return web_profile.id
            else:
                msg = "Web profile creation encountered error [%s]. Will continue without one" % (
                    web_profile.error
                )
                logger.warning(msg)

        except Exception:  # pylint: disable=broad-except
            logger.warning("Creating PayPal WebProfile resulted in exception. Will continue without one.")

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """
        Create a new Alipay payment.

        Arguments:
            basket (Basket): The basket of products being purchased.
            request (Request, optional): A Request object which is used to construct PayPal's `return_url`.
            use_client_side_checkout (bool, optional): This value is not used.
            **kwargs: Additional parameters; not used by this method.

        Returns:
            dict: PayPal-specific parameters required to complete a transaction. Must contain a URL
                to which users can be directed in order to approve a newly created payment.

        Raises:
            GatewayError: Indicates a general error or unexpected behavior on the part of PayPal which prevented
                a payment from being created.
        """
        return_url = urljoin(get_ecommerce_url(), reverse('alipay:execute'))
        data = {
            'intent': 'sale',
            'redirect_urls': {
                'return_url': return_url,
                'cancel_url': self.cancel_url,
            },
            'payer': {
                'payment_method': 'alipay',
            },
            'transactions': [{
                'amount': {
                    'total': unicode(basket.total_incl_tax),
                    'currency': basket.currency,
                },
                'item_list': {
                    'items': [
                        {
                            'quantity': line.quantity,
                            # PayPal requires that item names be at most 127 characters long.
                            'name': middle_truncate(line.product.title, 127),
                            # PayPal requires that the sum of all the item prices (where price = price * quantity)
                            # equals to the total amount set in amount['total'].
                            'price': unicode(line.line_price_incl_tax_incl_discounts / line.quantity),
                            'currency': line.stockrecord.price_currency,
                        }
                        for line in basket.all_lines()
                    ],
                },
                'invoice_number': basket.order_number,
            }],
        }

        if waffle.switch_is_active('create_and_set_webprofile'):
            locale_code = self.resolve_alipay_locale(request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME))
            web_profile_id = self.create_temporary_web_profile(locale_code)
            if web_profile_id is not None:
                data['experience_profile_id'] = web_profile_id
        else:
            try:
                web_profile = AlipayWebProfile.objects.get(name=self.DEFAULT_PROFILE_NAME)
                data['experience_profile_id'] = web_profile.id
            except AlipayWebProfile.DoesNotExist:
                pass

        available_attempts = 1
        if waffle.switch_is_active('PAYPAL_RETRY_ATTEMPTS'):
            available_attempts = self.retry_attempts

        for i in range(1, available_attempts + 1):
            try:
                payment = alipay_sdk.Payment(data, api=self.alipay_api)
                payment.create()
                if payment.success():
                    break
                else:
                    if i < available_attempts:
                        logger.warning(
                            u"Creating AliPay payment for basket [%d] was unsuccessful. Will retry.",
                            basket.id,
                            exc_info=True
                        )
                    else:
                        error = self._get_error(payment)
                        # pylint: disable=unsubscriptable-object
                        entry = self.record_processor_response(
                            error,
                            transaction_id=error['debug_id'],
                            basket=basket
                        )
                        logger.error(
                            u"%s [%d], %s [%d].",
                            "Failed to create AliPay payment for basket",
                            basket.id,
                            "AliPay's response recorded in entry",
                            entry.id,
                            exc_info=True
                        )
                        raise GatewayError(error)

            except:  # pylint: disable=bare-except
                if i < available_attempts:
                    logger.warning(
                        u"Creating AliPay payment for basket [%d] resulted in an exception. Will retry.",
                        basket.id,
                        exc_info=True
                    )
                else:
                    logger.exception(
                        u"After %d retries, creating AliPay payment for basket [%d] still experienced exception.",
                        i,
                        basket.id
                    )
                    raise

        entry = self.record_processor_response(payment.to_dict(), transaction_id=payment.id, basket=basket)
        logger.info("Successfully created AliPay payment [%s] for basket [%d].", payment.id, basket.id)
        id = payment.id
        order_string = self.alipay_api.api_alipay_trade_page_pay(
            out_trade_no=payment.id,
            total_amount=unicode(basket.total_incl_tax),#0.01,
            subject=middle_truncate(line.product.title, 127),
            return_url=return_url,
        )

        parameters = {
            'payment_page_url': self.alipay_api.default_endpoint() + '?' + order_string,
            #'payment_page_url': 'error_test',
        }

        return parameters

    def handle_processor_response(self, response, basket=None):
        """
        Execute an approved PayPal payment.

        This method creates PaymentEvents and Sources for approved payments.

        Arguments:
            response (dict): Dictionary of parameters returned by PayPal in the `return_url` query string.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            GatewayError: Indicates a general error or unexpected behavior on the part of PayPal which prevented
                an approved payment from being executed.

        Returns:
            HandledProcessorResponse
        """

        # By default PayPal payment will be executed only once.
        available_attempts = 1

        # Add retry attempts (provided in the configuration)
        # if the waffle switch 'ENABLE_PAYPAL_RETRY' is set
        if waffle.switch_is_active('PAYPAL_RETRY_ATTEMPTS'):
            available_attempts = available_attempts + self.retry_attempts

        for attempt_count in range(1, available_attempts + 1):
            payment = alipay_sdk.Payment.find(response.get('paymentId'), api=self.alipay_api)

            if payment.success():
                # On success break the loop.
                break

            # Raise an exception for payments that were not successfully executed. Consuming code is
            # responsible for handling the exception
            error = self._get_error(payment)
            # pylint: disable=unsubscriptable-object
            entry = self.record_processor_response(error, transaction_id=error['debug_id'], basket=basket)

            logger.warning(
                "Failed to execute PayPal payment on attempt [%d]. "
                "PayPal's response was recorded in entry [%d].",
                attempt_count,
                entry.id
            )

            # After utilizing all retry attempts, raise the exception 'GatewayError'
            if attempt_count == available_attempts:
                logger.error(
                    "Failed to execute PayPal payment [%s]. "
                    "PayPal's response was recorded in entry [%d].",
                    payment.id,
                    entry.id
                )
                raise GatewayError

        self.record_processor_response(payment.to_dict(), transaction_id=payment.id, basket=basket)
        logger.info("Successfully executed PayPal payment [%s] for basket [%d].", payment.id, basket.id)

        currency = payment.transactions[0].amount.currency
        total = Decimal(payment.transactions[0].amount.total)
        transaction_id = payment.id
        # payer_info.email may be None, see:
        # http://stackoverflow.com/questions/24090460/alipay-rest-api-return-empty-payer-info-for-non-us-accounts
        email = payment.payer.payer_info.email
        label = 'AliPay ({})'.format(email) if email else 'AliPay Account'

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=label,
            card_type=None
        )

    def _get_error(self, payment):
        """
        Shameful workaround for mocking the `error` attribute on instances of
        `alipayrestsdk.Payment`. The `error` attribute is created at runtime,
        but passing `create=True` to `patch()` isn't enough to mock the
        attribute in this module.
        """
        return payment.error  # pragma: no cover

    def _get_payment_sale(self, payment):
        """
        Returns the Sale related to a given Payment.

        Note (CCB): We mostly expect to have a single sale and transaction per payment. If we
        ever move to a split payment scenario, this will need to be updated.
        """
        for transaction in payment.transactions:
            for related_resource in transaction.related_resources:
                try:
                    return related_resource.sale
                except Exception:  # pylint: disable=broad-except
                    continue

        return None

    def issue_credit(self, order, reference_number, amount, currency):
        try:
            payment = alipay_sdk.Payment.find(reference_number, api=self.alipay_api)
            sale = self._get_payment_sale(payment)

            if not sale:
                logger.error('Unable to find a Sale associated with PayPal Payment [%s].', payment.id)

            refund = sale.refund({
                'amount': {
                    'total': unicode(amount),
                    'currency': currency,
                }
            })

        except:
            msg = 'An error occurred while attempting to issue a credit (via PayPal) for order [{}].'.format(
                order.number)
            logger.exception(msg)
            raise GatewayError(msg)

        basket = order.basket
        if refund.success():
            transaction_id = refund.id
            self.record_processor_response(refund.to_dict(), transaction_id=transaction_id, basket=basket)
            return transaction_id
        else:
            error = refund.error
            entry = self.record_processor_response(error, transaction_id=error['debug_id'], basket=basket)

            msg = "Failed to refund PayPal payment [{sale_id}]. " \
                  "PayPal's response was recorded in entry [{response_id}].".format(sale_id=sale.id,
                                                                                    response_id=entry.id)
            raise GatewayError(msg)
