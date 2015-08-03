define([
        'backbone',
        'underscore',
        'collections/product_collection',
        'models/course_seat_model'
    ],
    function (Backbone,
              _,
              ProductCollection,
              CourseSeatModel) {
        'use strict';

        return Backbone.Model.extend({
            urlRoot: '/api/v2/courses/',
            defaults: {
                name: ''
            },

            getProducts: function () {
                if (_.isUndefined(this._products)) {
                    this._products = new ProductCollection();
                    this._products.url = this.get('products_url');
                    return this._products.getFirstPage({fetch: true});
                }

                return this._products;
            },

            getSeats: function () {
                // Returns the seat products
                return this.getProducts().filter(function (product) {
                    // Filter out parent products since there is no need to display or modify.
                    return (product instanceof CourseSeatModel) && product.get('structure') !== 'parent';
                });
            }
        });
    }
);
