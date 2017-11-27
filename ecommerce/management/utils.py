import logging

from oscar.apps.partner import strategy
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.payment.helpers import get_processor_class_by_name

logger = logging.getLogger(__name__)

Applicator = get_class('offer.utils', 'Applicator')
Basket = get_model('basket', 'Basket')

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
