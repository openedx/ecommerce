define([
    'collections/course_collection',
    'views/course_list_view',
    'pages/page'
],
    function(CourseCollection,
              CourseListView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Courses'),

            initialize: function() {
                this.collection = new CourseCollection();
                this.view = new CourseListView({collection: this.collection});
                this.render();
                this.collection.fetch({remove: false, data: {page_size: 50}});
            }
        });
    }
);
