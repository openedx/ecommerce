REFUND_ORDER_EMAIL_SUBJECT = 'Your New edX Access Code'
REFUND_ORDER_EMAIL_GREETING = 'Hello! We see you unenrolled from a course provided by your organization within edX’s ' \
                              'refund window. As part of our policy, we are giving you a new code to use. You can ' \
                              'use this to enroll in any course that was available for you to enroll in with the ' \
                              'original code.'
REFUND_ORDER_EMAIL_CLOSING = 'We hope you find a course that meets your learning needs! For any questions, reach out ' \
                             'to your Learning Manager at your organization.'

# .. toggle_name: enable_hoist_order_history
# .. toggle_type: waffle_flag
# .. toggle_default: False
# .. toggle_description: Allows order fetching from Commerce Coordinator API for display in Order History MFE
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2022-04-05
# .. toggle_tickets: REV-2576
# .. toggle_status: supported
ENABLE_HOIST_ORDER_HISTORY = 'enable_hoist_order_history'

# .. toggle_name: enable_receipts_via_ecommerce_mfe
# .. toggle_type: waffle_flag
# .. toggle_default: False
# .. toggle_description: Determines whether to send user to new receipt page (vs old)
# .. toggle_use_cases: open_edx
# .. toggle_creation_date: 2022-06-02
# .. toggle_tickets: REV-2687
# .. toggle_status: supported
ENABLE_RECEIPTS_VIA_ECOMMERCE_MFE = 'enable_receipts_via_ecommerce_mfe'
