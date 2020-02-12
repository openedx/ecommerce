# Waffle switch used to enable/disable Enterprise offers.
ENTERPRISE_OFFERS_SWITCH = 'enable_enterprise_offers'

# Waffle switch used to enable/disable using Enterprise Offers for Coupons.
ENTERPRISE_OFFERS_FOR_COUPONS_SWITCH = 'enable_enterprise_offers_for_coupons'

# Waffle switch used to enable/disable using role based access control.
USE_ROLE_BASED_ACCESS_CONTROL = 'use_role_based_access_control'

COUPON_ERRORS = {
    'ENT_COUPON_000': 'The coupon is not valid for this course.',  # this needs extra message
    'ENT_COUPON_001': 'Coupon can not be redeemed because learner\'s email does not matches the coupon\'s email domain.',
    'ENT_COUPON_002': 'Coupon can not be redeemed due to invalid consent token.',
    'ENT_COUPON_003': 'Coupon can not be redeemed because the basket contains a product which is not course.',
    'ENT_COUPON_004': 'Coupon can not be redeemed because request failed to fetch learner data from LMS.',
    'ENT_COUPON_005': 'Coupon can not be redeemed because invalid learner data was returned from LMS.',
    'ENT_COUPON_006': 'Coupon can not be redeemed because learner enterprise does not match coupon enterprise.',
    'ENT_COUPON_007': 'Coupon can not be redeemed because course does not exist learner\'s enterprise catalog.',
    'ENT_COUPON_008': 'Coupon can not be redeemed because request failed to fetch course catalog data from LMS.',
    'ENT_COUPON_009': 'Coupon can not be redeemed because enterprise catalog does not contain the course in this basket.',
    'ENT_COUPON_010': 'Coupon can not be redeemed because it has not been assigned to this user and their are no remaining available uses.',
    'ENT_COUPON_011': 'The coupon is not valid for this basket.',  # this needs extra message
    'ENT_COUPON_012': 'Learner attempted to apply a code to an empty basket.',
    'ENT_COUPON_013': 'Learner tried to apply a code that is already applied.',
    'ENT_COUPON_014': 'The coupon is not valid for this basket.',  # this needs extra message
    'ENT_COUPON_015': 'The coupon could not be applied to this basket.',  # this needs extra message
    'ENT_COUPON_016': 'Coupon can not be redeemed because request failed to fetch catalog data from discovery service.',
    'ENT_COUPON_017': 'Coupon can not be redeemed because learner\'s email does not matches the coupon\'s email domain.',
    'ENT_COUPON_018': 'Coupon can not be redeemed because it can only be used on single item baskets.',
    'ENT_COUPON_019': 'Coupon can not be redeemed because it is not valid for all courses in basket.',
    'ENT_COUPON_020': 'Coupon can not be redeemed becuase discovery service is unreachable for catalogs endpoint.',
    'ENT_COUPON_021': 'Coupon can not be redeemed because catalog does not contain the course.',
}