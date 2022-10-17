import logging

from ecommerce.extensions.iap.api.v1.google_validator import GooglePlayValidator
from ecommerce.extensions.iap.processors.base_iap import BaseIAP


logger = logging.getLogger(__name__)


class AndroidIAP(BaseIAP):
    """
    Android IAP Rest API.
    """
    NAME = 'android-iap'
    TITLE = 'AndroidInAppPurchase'
    DEFAULT_PROFILE_NAME = 'default'

    def get_validator(self):
        return GooglePlayValidator()

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        raise NotImplementedError('The {} payment processor does not support credit issuance.'.format(self.NAME))
