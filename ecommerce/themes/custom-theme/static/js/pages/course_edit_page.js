define([
    'models/course_model',
    'pages/page',
    'views/course_create_edit_view'
],
    function(Course,
              Page,
              CourseCreateEditView) {
        'use strict';

        return Page.extend({
            title: function() {
                return this.model.get('name') + ' - ' + gettext('Edit Course');
            },

            initialize: function(options) {
                this.model = Course.findOrCreate({id: options.id});
                this.view = new CourseCreateEditView({
                    editing: true,
                    model: this.model
                });

                this.listenTo(this.model, 'sync', this.render);
                this.model.fetch({
                    data: {include_products: true}
                });
            }
        });
    }
);
