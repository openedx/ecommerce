import mock
from inapppy import errors
from oscar.test.factories import BasketFactory
from testfixtures import LogCapture

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.iap.api.v1.google_validator import GooglePlayValidator
from ecommerce.extensions.test.factories import create_basket
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
        "purchase_token": VALID_PURCHASE_TOKEN,
    }
    INVALID_RECEIPT = {
        "purchaseToken": INVALID_PURCHASE_TOKEN,
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
        self.basket = BasketFactory()
        self.course = CourseFactory()
        product = self.course.create_or_update_seat('verified', False, 50)
        self.basket = create_basket(price='50.0', product_class=product.product_class)

    @mock.patch('ecommerce.extensions.iap.api.v1.google_validator.GooglePlayVerifier')
    def test_validate_successful(self, mock_google_verifier):
        mock_google_verifier.return_value = GooglePlayVerifierProxy()
        response = self.validator.validate(self.VALID_RECEIPT, self.CONFIGURATION, self.basket)
        self.assertEqual(response, self.VALIDATED_RESPONSE)

    @mock.patch('ecommerce.extensions.iap.api.v1.google_validator.GooglePlayVerifier')
    def test_validate_failure(self, mock_google_verifier):
        mock_google_verifier.return_value = GooglePlayVerifierProxy()
        logger_name = 'ecommerce.extensions.iap.api.v1.google_validator'
        with LogCapture(logger_name) as google_validator_log_capture:
            response = self.validator.validate(self.INVALID_RECEIPT, self.CONFIGURATION, self.basket)
            google_validator_log_capture.check_present(
                (
                    logger_name,
                    'ERROR',
                    "Purchase validation failed, Now moving to fallback approach for non consumable skus"
                ),
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

    @mock.patch('ecommerce.extensions.iap.api.v1.google_validator.GooglePlayVerifier')
    def test_validate_failure_for_consumable_sku(self, mock_google_verifier):
        logger_name = 'ecommerce.extensions.iap.api.v1.google_validator'
        with mock.patch.object(GooglePlayVerifierProxy, 'verify_with_result',
                               side_effect=[errors.GoogleError(), GooglePlayVerifierResponse()]), \
                LogCapture(logger_name) as google_validator_log_capture:
            mock_google_verifier.return_value = GooglePlayVerifierProxy()

            response = self.validator.validate(self.INVALID_RECEIPT, self.CONFIGURATION, self.basket)
            google_validator_log_capture.check_present(
                (
                    logger_name,
                    'ERROR',
                    "Purchase validation failed, Now moving to fallback approach for non consumable skus"
                ),
            )
            self.assertEqual(response, self.VALIDATED_RESPONSE)
