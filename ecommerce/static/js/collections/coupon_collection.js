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
            url: '/api/v2/products/',

            /*
             * Return an array of products where product_class is Coupon.
             */
            parse: function (response) {
                var results = this._super(response);
                return _.where(results, { product_class: 'Coupon' });
            }
        });
    }
);
