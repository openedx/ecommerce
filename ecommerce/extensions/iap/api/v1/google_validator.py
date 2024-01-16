import logging

from inapppy import GooglePlayVerifier, errors

logger = logging.getLogger(__name__)


class GooglePlayValidator:
    def validate(self, receipt, configuration):
        """
        Accepts receipt, validates that the purchase has already been completed in
        Google for the mentioned productId.
        """
        purchase_token = receipt['purchaseToken']
        product_sku = receipt['productId']
        verifier = GooglePlayVerifier(
            configuration.get('google_bundle_id'),
            configuration.get('google_service_account_key_file'),
        )
        try:
            response = verifier.verify_with_result(purchase_token, product_sku, is_subscription=False)
            result = {
                'raw_response': response.raw_response,
                'is_canceled': response.is_canceled,
                'is_expired': response.is_expired
            }
        except errors.GoogleError as exc:
            logger.error('Purchase validation failed %s', exc)
            result = {
                'error': exc.raw_response,
                'message': exc.message
            }
        return result
