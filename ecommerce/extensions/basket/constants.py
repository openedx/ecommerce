TEMPORARY_BASKET_CACHE_KEY = "ecommerce.is_calculate_temporary_basket"
EMAIL_OPT_IN_ATTRIBUTE = "email_opt_in"
PURCHASER_BEHALF_ATTRIBUTE = "purchased_for_organization"
PAYMENT_INTENT_ID_ATTRIBUTE = "payment_intent_id"

# .. toggle_name: enable_stripe_payment_processor
# .. toggle_type: waffle_flag
# .. toggle_default: False
# .. toggle_description: Allows payments to be processed through Stripe instead of CyberSource
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2022-09-19
# .. toggle_tickets: REV-3004
# .. toggle_status: supported
ENABLE_STRIPE_PAYMENT_PROCESSOR = 'enable_stripe_payment_processor'
