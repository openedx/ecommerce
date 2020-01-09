define([
    'models/course_model',
    'views/course_detail_view',
    'pages/page'
],
    function(Course,
              CourseDetailView,
              Page) {
        'use strict';

        return Page.extend({
            title: function() {
                return this.model.get('name') + ' - ' + gettext('View Course');
            },

            initialize: function(options) {
                this.model = Course.findOrCreate({id: options.id});
                this.view = new CourseDetailView({model: this.model});
                this.listenTo(this.model, 'change sync', this.render);
                this.model.fetch({data: {include_products: true}});
            }
        });
    }
);
