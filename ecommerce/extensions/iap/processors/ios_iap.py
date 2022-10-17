import logging

from ecommerce.extensions.iap.api.v1.ios_validator import IOSValidator
from ecommerce.extensions.iap.processors.base_iap import BaseIAP


logger = logging.getLogger(__name__)


class IOSIAP(BaseIAP):
    """
    Android IAP Rest API.
    """
    NAME = 'ios-iap'
    TITLE = 'IOSInAppPurchase'

    def get_validator(self):
        return IOSValidator()

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        raise NotImplementedError('The {} payment processor does not support credit issuance.'.format(self.NAME))
