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
            fetch: function (options) {
                options = options || {};
                _.defaults(options.data || (options.data = {}), {
                    product_class__name: 'Coupon'
                });
                return this._super(options);
            }
        });
    }
);
