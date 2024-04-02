""" Constants for iap extension apis v1 """

COURSE_ADDED_TO_BASKET = "Course added to the basket successfully"
COURSE_ALREADY_PAID_ON_DEVICE = "The course upgrade has already been paid for by the user."
DISABLE_REDUNDANT_PAYMENT_CHECK_MOBILE_SWITCH_NAME = "disable_redundant_payment_check_for_mobile"
ERROR_ALREADY_PURCHASED = "You have already purchased these products"
ERROR_BASKET_NOT_FOUND = "Basket [{}] not found."
ERROR_BASKET_ID_NOT_PROVIDED = "Basket id is not provided"
ERROR_DURING_IOS_REFUND_EXECUTION = "Could not execute IOS refund."
ERROR_DURING_ORDER_CREATION = "An error occurred during order creation."
ERROR_DURING_PAYMENT_HANDLING = "An error occurred during payment handling."
ERROR_ORDER_NOT_FOUND_FOR_REFUND = "Could not find any order to refund for [%s] by processor [%s]"
ERROR_REFUND_NOT_COMPLETED = "Could not complete refund for user [%s] in course [%s] by processor [%s]"
ERROR_TRANSACTION_NOT_FOUND_FOR_REFUND = "Could not find any transaction to refund for [%s] by processor [%s]"
ERROR_DURING_POST_ORDER_OP = "An error occurred during post order operations."
EXPIRED_ANDROID_PURCHASE_ERROR = 'Android payment is expired for [%s] in basket [%d]'
FOUND_MULTIPLE_PRODUCTS_ERROR = "Found unexpected number of products for course [%s]"
GOOGLE_PUBLISHER_API_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
IOS_PRODUCT_REVIEW_NOTE = ('This in-app purchase will unlock all the content of the course {course_name}\n\n'
                           'For testing the end-to-end payment flow, please follow the following steps:\n1. '
                           'Go to the Discover tab\n2. Search for "{course_name}"\n3. Enroll in the course'
                           ' "{course_name}"\n4. Hit \"Upgrade to access more features\", it will open a '
                           'detail unlock features page\n5. Hit "Upgrade now for ${course_price}" from the'
                           ' detail page')
IGNORE_NON_REFUND_NOTIFICATION_FROM_APPLE = "Ignoring notification from apple since we are only expecting" \
                                            " refund notifications"
LOGGER_BASKET_ALREADY_PURCHASED = "Basket creation failed for user [%s] with SKUS [%s]. Products already purchased"
LOGGER_BASKET_CREATED = "Basket created for user [%s] with SKUS [%s]"
LOGGER_BASKET_CREATION_FAILED = "Basket creation failed for user [%s]. Error: [%s]"
LOGGER_BASKET_NOT_FOUND = "Basket [%s] not found for user [%s]."
LOGGER_CHECKOUT_ERROR = "Checkout failed with the error [%s] and status code [%s]."
LOGGER_EXECUTE_ALREADY_PURCHASED = "Execute payment failed for user [%s] and basket [%s]. " \
                                   "Products already purchased."
LOGGER_EXECUTE_GATEWAY_ERROR = "Execute payment validation failed for user [%s] and basket [%s]. Error: [%s]"
LOGGER_EXECUTE_ORDER_CREATION_FAILED = "Execute payment failed for user [%s] and basket [%s]. " \
                                       "Order Creation failed with error [%s]."
LOGGER_EXECUTE_PAYMENT_ERROR = "Execute payment failed for user [%s] and basket [%s]. " \
                               "Payment error [%s]."
LOGGER_EXECUTE_REDUNDANT_PAYMENT = "Execute payment failed for user [%s] and basket [%s]. " \
                                   "Redundant payment."
LOGGER_EXECUTE_STARTED = "Beginning Payment execution for user [%s], basket [%s], processor [%s]"
LOGGER_EXECUTE_SUCCESSFUL = "Payment execution successful for user [%s], basket [%s], processor [%s]"
LOGGER_PAYMENT_FAILED_FOR_BASKET = "Attempts to handle payment for basket [%s] failed with error [%s]."
LOGGER_REFUND_SUCCESSFUL = "Refund successful. OrderId: [%s] Processor: [%s] "
LOGGER_STARTING_PAYMENT_FLOW = "Starting payment flow for user [%s] for products [%s]."
MISSING_PRODUCT_ERROR = "Couldn't find parent product for course [%s]"
NO_PRODUCT_AVAILABLE = "No product is available to buy."
PRODUCTS_DO_NOT_EXIST = "Products with SKU(s) [{skus}] do not exist."
PRODUCT_IS_NOT_AVAILABLE = "Product [%s] is not available to buy."
RECEIVED_NOTIFICATION_FROM_APPLE = "Received notification from apple with notification type [%s]"
SEGMENT_MOBILE_BASKET_ADD = "Mobile Basket Add Items View Called"
SEGMENT_MOBILE_PURCHASE_VIEW = "Mobile Course Purchase View Called"
SKUS_CREATION_ERROR = "There was an error while creating mobile skus for course [%s]"
SKUS_CREATION_FAILURE = "Couldn't create mobile skus for course [%s]"
