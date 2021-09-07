from inapppy import AppStoreValidator, InAppPyValidationError
import logging

logger = logging.getLogger(__name__)


class IOSValidator:
    def validate(self, receipt, configuration):
        bundle_id = configuration.get('ios_bundle_id')
        # if True, automatically query sandbox endpoint if validation fails on production endpoint
        auto_retry_wrong_env_request = True
        validator = AppStoreValidator(bundle_id, auto_retry_wrong_env_request=auto_retry_wrong_env_request)

        try:
            exclude_old_transactions = False  # if True, include only the latest renewal transaction
            validation_result = validator.validate(receipt['purchaseToken'], exclude_old_transactions=exclude_old_transactions)
        except InAppPyValidationError as ex:
            # handle validation error
            logger.error('Purchase validation failed {}'.format(ex.raw_response))
            validation_result = {'error': ex.raw_response}

        return validation_result
