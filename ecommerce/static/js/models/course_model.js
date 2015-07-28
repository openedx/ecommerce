define([
        'backbone',
        'backbone.relational',
        'underscore',
        'collections/product_collection',
        'models/course_seat_model'
    ],
    function (Backbone,
              BackboneRelational,
              _,
              ProductCollection,
              CourseSeatModel) {
        'use strict';

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/courses/',

            defaults: {
                id: null,
                name: null,
                type: null
            },

            relations: [{
                type: Backbone.HasMany,
                key: 'products',
                relatedModel: CourseSeatModel,
                includeInJSON: false,
                parse: true
            }],

            getSeats: function () {
                // Returns the seat products

                var seats = this.get('products').filter(function (product) {
                        // Filter out parent products since there is no need to display or modify.
                        return (product instanceof CourseSeatModel) && product.get('structure') !== 'parent';
                    }),
                    seatTypes = _.map(seats, function (seat) {
                        return seat.get('certificate_type');
                    });

                return _.object(seatTypes, seats);
            }
        });
    }
);
