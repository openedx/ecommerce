import mock
from inapppy import errors
from testfixtures import LogCapture

from ecommerce.extensions.iap.api.v1.google_validator import GooglePlayValidator
from ecommerce.tests.testcases import TestCase

VALID_PURCHASE_TOKEN = "test.purchase.token"
INVALID_PURCHASE_TOKEN = "test.purchase.invalid_token"


class GooglePlayVerifierResponse:
    """ Class to create response object """

    def __init__(self):
        self.raw_response = '{}'
        self.is_canceled = False
        self.is_expired = False


class GooglePlayVerifierProxy:
    """ Proxy for inapppy.GooglePlayVerifier """

    def __init__(self):
        pass

    def verify_with_result(self, purchase_token, product_sku, is_subscription=False):  # pylint: disable=unused-argument
        if purchase_token == INVALID_PURCHASE_TOKEN:
            raise errors.GoogleError()

        return GooglePlayVerifierResponse()


class GoogleValidatorTests(TestCase):
    """ Google Validator Tests """

    PRODUCT_SKU = "test.product.sku"
    VALID_RECEIPT = {
        "purchaseToken": VALID_PURCHASE_TOKEN,
        "productId": PRODUCT_SKU
    }
    INVALID_RECEIPT = {
        "purchaseToken": INVALID_PURCHASE_TOKEN,
        "productId": PRODUCT_SKU
    }
    CONFIGURATION = {
        "google_bundle_id": "test.google.bundle.id",
        "google_service_account_key_file": "test.key.file"
    }
    VALIDATED_RESPONSE = {
        "raw_response": "{}",
        "is_canceled": False,
        "is_expired": False,
    }

    def setUp(self):
        self.validator = GooglePlayValidator()

    @mock.patch('ecommerce.extensions.iap.api.v1.google_validator.GooglePlayVerifier')
    def test_validate_successful(self, mock_google_verifier):
        mock_google_verifier.return_value = GooglePlayVerifierProxy()
        response = self.validator.validate(self.VALID_RECEIPT, self.CONFIGURATION)
        self.assertEqual(response, self.VALIDATED_RESPONSE)

    @mock.patch('ecommerce.extensions.iap.api.v1.google_validator.GooglePlayVerifier')
    def test_validate_failure(self, mock_google_verifier):
        mock_google_verifier.return_value = GooglePlayVerifierProxy()
        logger_name = 'ecommerce.extensions.iap.api.v1.google_validator'
        with LogCapture(logger_name) as google_validator_log_capture:
            response = self.validator.validate(self.INVALID_RECEIPT, self.CONFIGURATION)
            google_validator_log_capture.check_present(
                (
                    logger_name,
                    'ERROR',
                    "Purchase validation failed {}".format(
                        'GoogleError None None'
                    ),
                ),
            )
            self.assertIn('error', response)
            self.assertIn('message', response)
