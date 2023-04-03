from ecommerce.extensions.iap.api.v1.ios_validator import IOSValidator
from ecommerce.extensions.iap.processors.base_iap import BaseIAP
from ecommerce.extensions.payment.models import PaymentProcessorResponse


class IOSIAP(BaseIAP):  # pylint: disable=W0223
    """
    Android IAP Rest API.
    """
    NAME = 'ios-iap'
    TITLE = 'IOSInAppPurchase'

    def get_validator(self):
        return IOSValidator()

    def is_payment_redundant(self, original_transaction_id=None, transaction_id=None):
        """
        Return True if the original_transaction_id has previously been processed
        for a purchase.
        """
        return PaymentProcessorResponse.objects.filter(
            processor_name=self.NAME,
            extension__original_transaction_id=original_transaction_id).exists()
