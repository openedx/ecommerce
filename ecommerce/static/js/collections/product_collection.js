define([
        'collections/drf_pageable_collection',
        'models/product_model',
        'models/course_seats/course_seat',
        'utils/course_utils'
    ],
    function (DrfPageableCollection,
              Product,
              CourseSeat,
              CourseUtils) {
        'use strict';

        return DrfPageableCollection.extend({
            mode: 'client',

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
