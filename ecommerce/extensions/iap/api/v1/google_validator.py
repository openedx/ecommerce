from inapppy import GooglePlayVerifier, errors
import logging

logger = logging.getLogger(__name__)


class GooglePlayValidator:
    def validate(self, receipt, configuration):
        """
        Accepts receipt, validates in Google.
        """
        purchase_token = receipt['purchaseToken']
        product_sku = receipt['productId']
        verifier = GooglePlayVerifier(
            configuration.get('google_bundle_id'),
            configuration.get('google_service_account_key_file'),
        )
        try:
            result = verifier.verify_with_result(
                purchase_token,
                product_sku,
                is_subscription=False
            )
        except errors.GoogleError as exc:
            logger.error('Purchase validation failed {}'.format(exc))
            result = dict(error=exc)
        return result
