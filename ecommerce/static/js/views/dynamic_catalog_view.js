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

            getRowData: function (seat) {
                var course_key_attr = _.find(seat.attribute_values, function(attr) {
                    if (attr.name === 'course_key'){
                        return attr;
                    }
                });
                var certificate_type = _.find(seat.attribute_values, function(attr) {
                    if (attr.name === 'certificate_type'){
                        return attr;
                    }
                });
                return {
                    id: course_key_attr.value,
                    name: seat.title,
                    type: _s(certificate_type.value).capitalize().value()
                };
            },

            previewCatalog: function (event) {
                this.limit = 10;
                this.offset = 0;
                event.preventDefault();
                if (!$.fn.dataTable.isDataTable('#seatsTable') ||
                    (this.used_query !== this.query || this.used_seat_types !== this.seat_types)
                ) {
                    this.table = this.$('#seatsTable').DataTable({
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
                                title: gettext('Seat title'),
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
                var tableData = data.seats.map(this.getRowData, this);
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
