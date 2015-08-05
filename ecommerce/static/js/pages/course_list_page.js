define([
        'collections/course_collection',
        'views/course_list_view',
        'pages/page'
    ],
    function (CourseCollection,
              CourseListView,
              Page) {
        'use strict';

        return Page.extend({
            title: 'Courses',

            initialize: function () {
                this.collection = new CourseCollection();
                this.view = new CourseListView({collection: this.collection});
                this.listenTo(this.collection, 'reset', this.render);
                this.collection.fetch({reset: true});
            }
        });
    }
);
