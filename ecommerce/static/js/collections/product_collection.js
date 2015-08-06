define([
        'backbone',
        'models/product_model',
        'models/course_seats/course_seat',
        'utils/course_utils'
    ],
    function (Backbone,
              Product,
              CourseSeat,
              CourseUtils) {
        'use strict';

        return Backbone.Collection.extend({
            model: function (attrs, options) {
                var modelClass = Product;
                if (attrs.product_class === 'Seat') {
                    modelClass = CourseUtils.getCourseSeatModel(CourseUtils.getSeatType(attrs));
                }

                return new modelClass(attrs, options);
            }
        });
    }
);
