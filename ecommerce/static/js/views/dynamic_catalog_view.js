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
                'click [name=preview_catalog]': 'previewCatalog',
                'click .pagination .disabled, .pagination .active': 'stopEventPropagation'
            },

            initialize: function (options) {
                this.query = options.query;
                this.seat_types = options.seat_types;
                this._super();
            },

            stopEventPropagation: function(event) {
                event.stopPropagation();
            },

            getRowData: function (course) {
                return {
                    id: course.id,
                    name: course.name,
                    type: _s(course.type).capitalize().value()
                };
            },

            previewCatalog: function (event) {
                this.limit = 10;
                this.offset = 0;
                event.preventDefault();
                if (!$.fn.dataTable.isDataTable('#coursesTable') || 
                    (this.used_query !== this.query || this.used_seat_types !== this.seat_types)
                ) {
                    this.table = this.$('#coursesTable').DataTable({
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
                        ]
                    }, this).clear().draw();
                    this.used_query = this.query;
                    this.used_seat_types = this.seat_types;
                    this.fetchCourseData();
                }
            },

            fetchCourseData: function() {
                Backbone.ajax({
                    context: this,
                    type: 'GET',
                    url: window.location.origin + '/api/v2/catalogs/preview/',
                    data: {
                        query : this.query,
                        seat_types: this.seat_types.join(),
                        limit: this.limit,
                        offset: this.offset
                    },
                    success: this.onSuccess
                });
            },

            onSuccess: function(data) {
                var tableData = data.courses.map(this.getRowData, this);
                this.table.rows.add(tableData).draw();
                if (data.next) {
                    this.offset += this.limit;
                    setTimeout(_.bind(this.fetchCourseData, this), 500);
                }
            },

            render: function () {
                this.$el.html(this.template({}));
                return this;
            }
        });
    });
