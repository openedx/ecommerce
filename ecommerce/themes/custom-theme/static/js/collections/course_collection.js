define([
    'collections/paginated_collection',
    'models/course_model'
],
    function(PaginatedCollection,
              Course) {
        'use strict';

        return PaginatedCollection.extend({
            model: Course,
            url: '/api/v2/courses/'
        });
    }
);
