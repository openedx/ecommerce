define([
        'collections/drf_pageable_collection',
        'models/product_model',
        'models/course_seat_model'
    ],
    function (DrfPageableCollection, ProductModel, CourseSeatModel) {
        'use strict';

        return DrfPageableCollection.extend({
            mode: 'client',
            model: function (attrs, options) {
                var modelClass = ProductModel;
                if (attrs.product_class === 'Seat') {
                    modelClass = CourseSeatModel;
                }

                return new modelClass(attrs, options);
            }
        });
    });
