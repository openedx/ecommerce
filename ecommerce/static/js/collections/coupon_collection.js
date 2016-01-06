define([
        'backbone',
        'underscore',
        'collections/paginated_collection',
        'models/coupon_model'
    ],
    function (Backbone,
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
                return PaginatedCollection.prototype.fetch.call(this, options);
            }
        });
    }
);
