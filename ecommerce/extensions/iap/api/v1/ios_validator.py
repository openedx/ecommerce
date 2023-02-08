import logging

from inapppy import AppStoreValidator, InAppPyValidationError

logger = logging.getLogger(__name__)


class IOSValidator:
    def validate(self, receipt, configuration):
        """
        Accepts receipt, validates that the purchase has already been completed in
        Apple for the mentioned productId.
        """
        bundle_id = configuration.get('ios_bundle_id')
        # If True, automatically query sandbox endpoint if validation fails on production endpoint
        # TODO: Add auto_retry_wrong_env_request to environment variables
        auto_retry_wrong_env_request = True
        validator = AppStoreValidator(bundle_id, auto_retry_wrong_env_request=auto_retry_wrong_env_request)

        try:
            validation_result = validator.validate(
                receipt['purchaseToken'],
                exclude_old_transactions=False  # if True, include only the latest renewal transaction
            )
        except InAppPyValidationError as ex:
            # handle validation error
            logger.error('Purchase validation failed %s', ex.raw_response)
            validation_result = {'error': ex.raw_response}

        return validation_result
