# Waffle switch used to enable/disable Enterprise offers.
ENTERPRISE_OFFERS_SWITCH = 'enable_enterprise_offers'

# Waffle switch used to enable/disable using Enterprise Offers for Coupons.
ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH = 'enable_enterprise_offers_for_coupons'

# Waffle switch used to enable/disable using role based access control.
USE_ROLE_BASED_ACCESS_CONTROL = 'use_role_based_access_control'

# Waffle flag used to switch over ecommerce's usage of the enterprise catalog service
USE_ENTERPRISE_CATALOG = 'use_enterprise_catalog'

# Default Sender Alias used in Enterprise Customer Code Assign,Remind and Revoke Emails.

SENDER_ALIAS = 'edX Support Team'

# Salesforce Opportunity ID must be 18 alphanumeric characters and begin with 006 OR be "none" (to accommodate
# potential edge case).
ENTERPRISE_SALES_FORCE_ID_REGEX = r'^006[a-zA-Z0-9]{15}$|^none$'

# Salesforce Opportunity Opportunity Line item must be 18 alphanumeric characters
# and begin with a number OR be "none" (to accommodate potential edge case).
ENTERPRISE_SALESFORCE_OPPORTUNITY_LINE_ITEM_REGEX = r'^[0-9]{1}[a-zA-Z0-9]{17}$|^none$'
