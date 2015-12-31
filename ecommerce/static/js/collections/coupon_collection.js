define([
        'backbone',
        'backbone.super',
        'underscore',
        'collections/paginated_collection',
        'models/coupon_model'
    ],
    function (Backbone,
              BackboneSuper,
              _,
              PaginatedCollection,
              CouponModel) {
        'use strict';

        return PaginatedCollection.extend({
            model: CouponModel,
            url: '/api/v2/coupons/'
        });
    }
);
