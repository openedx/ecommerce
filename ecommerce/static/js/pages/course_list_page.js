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
                this.view = new CourseListView();
                this.render();
            }
        });
    }
);
