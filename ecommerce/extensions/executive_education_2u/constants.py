class ExecutiveEducation2UCheckoutFailureReason:
    NO_OFFER_AVAILABLE = 'no_offer_available'
    NO_OFFER_WITH_ENOUGH_BALANCE = 'no_offer_with_enough_balance'
    NO_OFFER_WITH_ENOUGH_USER_BALANCE = 'no_offer_with_enough_user_balance'
    NO_OFFER_WITH_REMAINING_APPLICATIONS = 'no_offer_with_remaining_applications'
    SYSTEM_ERROR = 'system_error'


class ExecutiveEducation2UCheckoutSegmentEvents:
    REDIRECTED_TO_LP = 'edx.bi.ecommerce.executive-education-2u.begin_checkout.redirected_to_lp'
    REDIRECTED_TO_LP_WITH_ERROR = 'edx.bi.ecommerce.executive-education-2u.begin_checkout.redirected_to_lp_with_error'
    REDIRECTED_TO_RECEIPT_PAGE = 'edx.bi.ecommerce.executive-education-2u.begin_checkout.redirected_to_receipt_page'
    ORDER_CREATED = 'edx.bi.ecommerce.executive-education-2u.finish_checkout.order_created'
