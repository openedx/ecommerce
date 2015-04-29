import json

from oscar.core.loading import get_model

from ecommerce.extensions.payment.constants import CARD_TYPES
from ecommerce.extensions.payment.helpers import sign


Order = get_model('order', 'Order')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

DEFAULT_CARD_TYPE = 'visa'


class PaymentEventsMixin(object):
    def get_order(self, basket):
        """ Return the order associated with a basket. """
        return Order.objects.get(basket=basket)

    def assert_processor_response_recorded(self, processor_name, transaction_id, response, basket=None):
        """ Ensures a PaymentProcessorResponse exists for the corresponding processor and response. """
        ppr = PaymentProcessorResponse.objects.get(processor_name=processor_name, transaction_id=transaction_id)
        self.assertEqual(ppr.response, response)
        self.assertEqual(ppr.basket, basket)

    def assert_valid_payment_event_fields(self, payment_event, amount, payment_event_type, processor_name, reference):
        """ Ensures the given PaymentEvent's fields match the specified values. """
        self.assertEqual(payment_event.amount, amount)
        self.assertEqual(payment_event.event_type, payment_event_type)
        self.assertEqual(payment_event.reference, reference)
        self.assertEqual(payment_event.processor_name, processor_name)

    def assert_payment_event_exists(self, basket, payment_event_type, reference, processor_name):
        """ Validates that a single PaymentEvent exists for the basket's associated order. """
        order = self.get_order(basket)
        self.assertEqual(order.payment_events.count(), 1)

        payment_event = order.payment_events.first()
        amount = basket.total_incl_tax
        self.assert_valid_payment_event_fields(payment_event, amount, payment_event_type, processor_name, reference)

    def assert_basket_matches_source(self, basket, source, source_type, reference, label):
        """
        Validates that the Source has the correct SourceType and that currency and amounts match the given Basket.
        """
        total = basket.total_incl_tax
        self.assertEqual(source.source_type, source_type)
        self.assertEqual(source.currency, basket.currency)
        self.assertEqual(source.amount_allocated, total)
        self.assertEqual(source.amount_debited, total)
        self.assertEqual(source.reference, reference)
        self.assertEqual(source.label, label)
        self.assertEqual(source.card_type, DEFAULT_CARD_TYPE)

    def assert_payment_source_exists(self, basket, source_type, reference, label):
        """ Validates that a single Source exists for the basket's associated order. """
        order = self.get_order(basket)
        self.assertEqual(order.sources.count(), 1)

        source = order.sources.first()
        self.assert_basket_matches_source(basket, source, source_type, reference, label)


class CybersourceMixin(object):
    """ Mixin with helper methods for testing CyberSource notifications. """

    def generate_signature(self, secret_key, data):
        """ Generate a signature for the given data dict. """
        keys = data[u'signed_field_names'].split(u',')

        message = u','.join([u'{key}={value}'.format(key=key, value=data[key]) for key in keys])
        return sign(message, secret_key)

    def generate_notification(self, secret_key, basket, decision=u'ACCEPT', billing_address=None, auth_amount=None,
                              tracking_context=None, **kwargs):
        """ Generates a dict containing the API reply fields expected to be received from CyberSource. """

        req_reference_number = kwargs.get('req_reference_number', unicode(basket.id))
        total = unicode(basket.total_incl_tax)
        auth_amount = auth_amount or total
        notification = {
            u'decision': decision,
            u'req_reference_number': req_reference_number,
            u'transaction_id': u'123456',
            u'auth_amount': auth_amount,
            u'req_amount': total,
            u'req_tax_amount': u'0.00',
            u'req_currency': basket.currency,
            u'req_card_number': u'xxxxxxxxxxxx1111',
            u'req_card_type': CARD_TYPES[DEFAULT_CARD_TYPE]['cybersource_code']
        }

        if billing_address:
            notification.update({
                u'req_bill_to_forename': billing_address.first_name,
                u'req_bill_to_surname': billing_address.last_name,
                u'req_bill_to_address_line1': billing_address.line1,
                u'req_bill_to_address_city': billing_address.line4,
                u'req_bill_to_address_postal_code': billing_address.postcode,
                u'req_bill_to_address_state': billing_address.state,
                u'req_bill_to_address_country': billing_address.country.iso_3166_1_a2
            })

            # Address Line 2 is an optional response field
            if billing_address.line2:
                notification[u'req_bill_to_address_line2'] = billing_address.line2

        if tracking_context is not None:
            notification['req_merchant_secure_data4'] = json.dumps({'tracking_context': tracking_context})

        notification[u'signed_field_names'] = u','.join(notification.keys())
        notification[u'signature'] = self.generate_signature(secret_key, notification)
        return notification
