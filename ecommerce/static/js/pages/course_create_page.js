define([
    'models/course_model',
    'views/course_create_edit_view',
    'pages/page'
],
    function(Course,
              CourseCreateEditView,
              Page) {
        'use strict';

        return Page.extend({
            title: gettext('Create New Course'),

            initialize: function() {
                this.model = new Course({});
                this.view = new CourseCreateEditView({model: this.model});
                this.render();
            }
        });
    }
);
