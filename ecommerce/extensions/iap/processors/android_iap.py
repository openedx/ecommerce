import logging

from oscar.apps.payment.exceptions import GatewayError
from urllib.parse import urljoin
import waffle

from django.urls import reverse

from ecommerce.extensions.iap.api.v1.google_validator import GooglePlayValidator
from ecommerce.extensions.iap.processors.base_iap import BaseIAP

from ecommerce.extensions.iap.models import IAPProcessorConfiguration
from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse


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
