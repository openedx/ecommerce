define([
    'collections/paginated_collection',
    'models/coupon_model'
],
    function(PaginatedCollection,
              CouponModel) {
        'use strict';

        return PaginatedCollection.extend({
            model: CouponModel,
            url: '/api/v2/coupons/'
        });
    }
);
