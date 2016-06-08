define(['jquery',
        'backbone',
        'underscore.string',
        'collections/course_collection',
        'text!templates/dynamic_catalog_buttons.html'
    ],
    function ($,
              Backbone,
              _s,
              Courses,
              DynamicCatalogButtons) {
        'use strict';

        return Backbone.View.extend({
            template: _.template(DynamicCatalogButtons),

            events: {
                'click [name=preview_catalog]': 'previewCatalog'
            },

            initialize: function (options) {
                this.query = options.query;
                this.seat_types = options.seat_types;

                this.courses = new Courses();

                this._super();
            },

            getRowData: function (course) {
                return {
                    id: course.get('id'),
                    name: course.get('name'),
                    type: _s(course.get('type')).capitalize().value()
                };
            },

            previewCatalog: function (event) {
                event.preventDefault();
                this.courses.fetch();

                Backbone.ajax({
                    context: this,
                    type: 'GET',
                    url: window.location.origin + '/api/v2/catalogs/preview/',
                    data: {
                        query : this.query
                    },
                    success: this.onSuccess
                });
            },

            filterCourses: function (course_keys, seat_types) {
                return _.filter(this.courses.models, function(course) {
                    return (_.contains(course_keys, course.get('id')) && _.contains(seat_types, course.get('type')));
                });
            },

            onSuccess: function(data) {
                var course_keys = _.pluck(data.results, 'key'),
                    course_data = this.filterCourses(course_keys, this.seat_types);

                this.$el.find('#coursesTable').DataTable({
                    autoWidth: false,
                    destroy: true,
                    info: true,
                    paging: true,
                    ordering: false,
                    searching: false,
                    columns: [
                        {
                            title: gettext('Course ID'),
                            data: 'id'
                        },
                        {
                            title: gettext('Course name'),
                            data: 'name'
                        },
                        {
                            title: gettext('Seat type'),
                            data: 'type'
                        }
                    ],
                    data: course_data.map(this.getRowData, this)
                }, this);
            },

            render: function () {
                this.$el.html(this.template({}));
                return this;
            }
        });
    });
