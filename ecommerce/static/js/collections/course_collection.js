define([
        'backbone',
        'underscore',
        'collections/paginated_collection',
        'models/course_model'
    ],
    function (Backbone,
              _,
              PaginatedCollection,
              CourseModel) {
        'use strict';

        return PaginatedCollection.extend({
            model: CourseModel,
            url: '/api/v2/courses/'
        });
    }
);
