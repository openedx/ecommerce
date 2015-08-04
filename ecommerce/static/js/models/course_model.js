define([
        'backbone',
        'backbone-relational',
        'backbone-validation',
        'underscore',
        'collections/product_collection',
        'models/course_seat_model'
    ],
    function (Backbone,
              BackboneRelational,
              BackboneValidation,
              _,
              ProductCollection,
              CourseSeatModel) {
        'use strict';

        Backbone.Validation.configure({
            labelFormatter: 'label'
        });

        _.extend(Backbone.Model.prototype, Backbone.Validation.mixin);

        _.extend(Backbone.Validation.patterns, {
            courseId: /[^/+]+(\/|\+)[^/+]+(\/|\+)[^/]+/
        });

        _.extend(Backbone.Validation.messages, {
            courseId: gettext('The course ID is invalid.')
        });

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/courses/',

            defaults: {
                id: null,
                name: null,
                type: null
            },

            validation: {
                id: {
                    required: true,
                    pattern: 'courseId'
                },
                name: {
                    required: true
                },
                type: {
                    required: true,
                    msg: gettext('You must select a course type.')
                }
            },

            labels: {
                id: 'Course ID',
                name: 'Course Name',
                type: 'Course Type'
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
