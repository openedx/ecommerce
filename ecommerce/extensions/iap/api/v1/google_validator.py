import logging

from inapppy import GooglePlayVerifier, errors

from ecommerce.extensions.iap.utils import get_consumable_android_sku

logger = logging.getLogger(__name__)


class GooglePlayValidator:
    def validate(self, receipt, configuration, basket=None):
        """
        Accepts receipt, validates that the purchase has already been completed in
        Google for the mentioned productId.
        """
        purchase_token = receipt['purchaseToken']
        # Mobile assumes one course is purchased at a time
        product_sku = get_consumable_android_sku(basket.total_excl_tax)
        verifier = GooglePlayVerifier(
            configuration.get('google_bundle_id'),
            configuration.get('google_service_account_key_file'),
        )
        try:
            result = self.verify_result(verifier, purchase_token, product_sku)
        except errors.GoogleError:
            try:
                # Fallback to the old approach and verify token with partner_sku
                # This fallback is temporary until all android products are switched to consumable products.
                result = self.verify_result(verifier, purchase_token, receipt['productId'])
            except errors.GoogleError as exc:
                logger.error('Purchase validation failed %s', exc)
                result = {
                    'error': exc.raw_response,
                    'message': exc.message
                }
        return result

    def verify_result(self, verifier, purchase_token, product_sku):
        response = verifier.verify_with_result(purchase_token, product_sku, is_subscription=False)
        result = {
            'raw_response': response.raw_response,
            'is_canceled': response.is_canceled,
            'is_expired': response.is_expired
        }
        return result
