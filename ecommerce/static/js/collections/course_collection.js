define([
        'backbone',
        'underscore',
        'models/course_model'
    ],
    function (Backbone,
              _,
              CourseModel) {
        'use strict';

        return Backbone.Collection.extend({
            model: CourseModel,
            url: '/api/v2/courses/',

            parse: function (response) {
                // Continue retrieving the remaining data
                if (response.next) {
                    this.url = response.next;
                    this.fetch({remove: false});
                }

                return response.results;
            }
        });
    }
);
