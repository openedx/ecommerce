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
