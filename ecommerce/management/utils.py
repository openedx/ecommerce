import logging

from oscar.apps.partner import strategy
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.constants import CYBERSOURCE_CARD_TYPE_MAP
from ecommerce.extensions.payment.helpers import get_processor_class_by_name
from ecommerce.extensions.payment.processors import HandledProcessorResponse

logger = logging.getLogger(__name__)

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')
NoShippingRequired = get_class('shipping.methods', 'NoShippingRequired')
OrderTotalCalculator = get_class('checkout.calculators', 'OrderTotalCalculator')

_payment_processors = {}


def _get_payment_processor(site, name):
    key = (site, name,)
    payment_processor = _payment_processors.get(key)

    if not payment_processor:
        payment_processor = get_processor_class_by_name(name)(site)
        _payment_processors[key] = payment_processor

    return payment_processor


def refund_basket_transactions(site, basket_ids):
    baskets = Basket.objects.filter(site=site, id__in=basket_ids)

    success_count = 0
    failure_count = 0

    for basket in baskets:
        basket.strategy = strategy.Default()
        Applicator().apply(basket, basket.owner, None)

        logger.info('Refunding transactions for basket [%d]...', basket.id)
        transactions = set(
            list(basket.paymentprocessorresponse_set.values_list('processor_name', 'transaction_id')))

        for processor_name, transaction_id in transactions:
            try:
                logger.info('Issuing credit for [%s] transaction [%s] made against basket [%d]...', processor_name,
                            transaction_id, basket.id)
                payment_processor = _get_payment_processor(site, processor_name)
                payment_processor.issue_credit(basket.order_number, basket, transaction_id, basket.total_excl_tax,
                                               basket.currency)
                success_count += 1
                logger.info('Successfully issued credit for [%s] transaction [%s] made against basket [%d].',
                            processor_name, transaction_id, basket.id)
            except Exception:  # pylint: disable=broad-except
                failure_count += 1
                logger.exception('Failed to issue credit for [%s] transaction [%s] made against basket [%d].',
                                 processor_name, transaction_id, basket.id)
        logger.info('Finished processing refunds for basket [%d].', basket.id)

    msg = 'Finished refunding basket transactions. [{success_count}] transactions were successfully refunded. ' \
          '[{failure_count}] attempts failed.'.format(success_count=success_count, failure_count=failure_count)
    logger.info(msg)

    return success_count, failure_count


class FulfillFrozenBaskets(EdxOrderPlacementMixin):

    def fulfill_basket(self, basket_id, site):

        logger.info('Trying to create order for frozen basket %d', basket_id)

        try:
            basket = Basket.objects.get(id=basket_id)
        except Basket.DoesNotExist:
            logger.info('Basket %d does not exist', basket_id)
            return False

        basket.strategy = strategy.Default()
        Applicator().apply(basket, user=basket.owner)

        transaction_responses = basket.paymentprocessorresponse_set.filter(transaction_id__isnull=False)
        unique_transaction_ids = set([response.transaction_id for response in transaction_responses])

        if len(unique_transaction_ids) > 1:
            logger.info('Basket %d has more than one transaction id, not Fulfilling', basket_id)
            return False

        response = transaction_responses[0]
        if response.transaction_id.startswith('PAY'):
            card_number = 'PayPal Account'
            card_type = None
            self.payment_processor = _get_payment_processor(site, 'paypal')
        else:
            card_number = response.response['req_card_number']
            card_type = CYBERSOURCE_CARD_TYPE_MAP.get(response.response['req_card_type'])
            self.payment_processor = _get_payment_processor(site, 'cybersource')

        handled_response = HandledProcessorResponse(
            transaction_id=response.transaction_id,
            total=basket.total_excl_tax,
            currency=basket.currency,
            card_number=card_number,
            card_type=card_type
        )

        try:
            self.record_payment(basket=basket, handled_processor_response=handled_response)

            shipping_method = NoShippingRequired()
            shipping_charge = shipping_method.calculate(basket)
            order_total = OrderTotalCalculator().calculate(basket, shipping_charge)

            user = basket.owner
            # Given a basket, order number generation is idempotent. Although we've already
            # generated this order number once before, it's faster to generate it again
            # than to retrieve an invoice number from PayPal.
            order_number = basket.order_number

            self.handle_order_placement(
                order_number=order_number,
                user=user,
                basket=basket,
                shipping_address=None,
                shipping_method=shipping_method,
                shipping_charge=shipping_charge,
                billing_address=None,
                order_total=order_total,
            )

            return True
        except:  # pylint: disable=bare-except
            logger.exception('Unable to fulfill basket %d', basket.id)
            return False
