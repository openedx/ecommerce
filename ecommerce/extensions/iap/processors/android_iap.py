import logging

from ecommerce.extensions.iap.api.v1.google_validator import GooglePlayValidator
from ecommerce.extensions.iap.processors.base_iap import BaseIAP

logger = logging.getLogger(__name__)


class AndroidIAP(BaseIAP):  # pylint: disable=W0223
    """
    Android IAP Rest API.
    """
    NAME = 'android-iap'
    TITLE = 'AndroidInAppPurchase'
    DEFAULT_PROFILE_NAME = 'default'

    def get_validator(self):
        return GooglePlayValidator()
