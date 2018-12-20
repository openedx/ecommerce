define([
    'collections/paginated_collection',
    'models/enterprise_coupon_model'
],
    function(PaginatedCollection,
              CouponModel) {
        'use strict';

        return PaginatedCollection.extend({
            model: CouponModel,
            url: '/api/v2/enterprise/coupons/'
        });
    }
);
