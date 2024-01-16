from ecommerce.extensions.iap.api.v1.google_validator import GooglePlayValidator
from ecommerce.extensions.iap.processors.base_iap import BaseIAP
from ecommerce.extensions.payment.models import PaymentProcessorResponse


class AndroidIAP(BaseIAP):  # pylint: disable=W0223
    """
    Android IAP Rest API.
    """
    NAME = 'android-iap'
    TITLE = 'AndroidInAppPurchase'
    DEFAULT_PROFILE_NAME = 'default'

    def get_validator(self):
        return GooglePlayValidator()

    def is_payment_redundant(self, original_transaction_id=None, transaction_id=None):
        """
        Return True if the transaction_id has previously been processed for a purchase.
        """
        return PaymentProcessorResponse.objects.filter(
            processor_name=self.NAME,
            transaction_id=transaction_id).exists()
