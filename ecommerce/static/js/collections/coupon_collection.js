define([
        'backbone',
        'underscore',
        'models/coupon_model'
    ],
    function (Backbone,
              _,
              CouponModel) {
        'use strict';

        return Backbone.Collection.extend({
            model: CouponModel,
            url: '/api/v2/coupons/',

            parse: function (response) {
                // Continue retrieving the remaining data
                if (response.next) {
                    this.url = response.next;
                    this.fetch({remove: false});
                }

                return response.results;
            }
        });
    }
);
