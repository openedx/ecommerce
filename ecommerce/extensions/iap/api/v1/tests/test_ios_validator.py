import mock
from inapppy import InAppPyValidationError
from testfixtures import LogCapture

from ecommerce.extensions.iap.api.v1.ios_validator import IOSValidator
from ecommerce.tests.testcases import TestCase

VALID_PURCHASE_TOKEN = "test.purchase.token"
INVALID_PURCHASE_TOKEN = "test.purchase.invalid_token"
SAMPLE_VALID_RESPONSE = {
    'message': 'valid_response'
}


class AppStoreValidatorProxy:
    """ Proxy for inapppy.AppStoreValidator """

    def __init__(self):
        pass

    def validate(self, purchase_token, exclude_old_transactions=False):  # pylint: disable=unused-argument
        if purchase_token == INVALID_PURCHASE_TOKEN:
            raise InAppPyValidationError()
        return SAMPLE_VALID_RESPONSE


class IOSValidatorTests(TestCase):
    """ IOS Validator Tests """

    VALID_RECEIPT = {
        "purchaseToken": VALID_PURCHASE_TOKEN,
    }
    INVALID_RECEIPT = {
        "purchaseToken": INVALID_PURCHASE_TOKEN,
    }

    def setUp(self):
        self.validator = IOSValidator()

    @mock.patch('ecommerce.extensions.iap.api.v1.ios_validator.AppStoreValidator')
    def test_validate_successful(self, mock_appstore_validator):
        mock_appstore_validator.return_value = AppStoreValidatorProxy()
        response = self.validator.validate(self.VALID_RECEIPT, {})
        self.assertEqual(response, SAMPLE_VALID_RESPONSE)

    @mock.patch('ecommerce.extensions.iap.api.v1.ios_validator.AppStoreValidator')
    def test_validate_failed(self, mock_appstore_validator):
        mock_appstore_validator.return_value = AppStoreValidatorProxy()
        logger_name = 'ecommerce.extensions.iap.api.v1.ios_validator'
        with LogCapture(logger_name) as ios_validator_log_capture:
            response = self.validator.validate(self.INVALID_RECEIPT, {})
            ios_validator_log_capture.check_present(
                (
                    logger_name,
                    'ERROR',
                    "Purchase validation failed {}".format(
                        'None'
                    ),
                ),
            )
            self.assertIn('error', response)
