// jscs:disable requireCapitalizedConstructors

define([
        'views/course_seat_form_fields/course_seat_form_field_view',
        'views/course_seat_form_fields/credit_course_seat_form_field_row_view',
        'text!templates/credit_course_seat_form_field.html',
        'utils/course_utils',
        'utils/utils'
    ],
    function (CourseSeatFormFieldView,
              CreditCourseSeatFormFieldRowView,
              FieldTemplate,
              CourseUtils,
              Utils) {
        'use strict';

        return CourseSeatFormFieldView.extend({
            certificateType: 'credit',
            idVerificationRequired: true,
            seatType: 'credit',
            template: _.template(FieldTemplate),
            rowView: CreditCourseSeatFormFieldRowView,

            events: {
                'click .add-seat': 'addSeatTableRow'
            },

            className: function () {
                return 'row ' + this.seatType;
            },

            initialize: function (options) {
                this.course = options.course;

                Utils.bindValidation(this);
            },

            render: function () {
                this.renderSeatTable();

                return this;
            },

            /**
             * Renders a table of course seats sharing a common seat type.
             */
            renderSeatTable: function () {
                var row,
                    $tableBody,
                    rows = [];

                this.$el.html(this.template());
                $tableBody = this.$el.find('tbody');

                // Instantiate new Views handling data binding for each Model in the Collection.
                this.collection.each( function (seat) {
                    row = new this.rowView({
                        model: seat,
                        isRemovable: false,
                        course: this.course
                    });

                    row.render();
                    rows.push(row.el);
                }, this);

                $tableBody.append(rows);

                return this;
            },

            /**
             * Adds a new row to the seat table.
             */
            addSeatTableRow: function () {
                var seatClass = CourseUtils.getCourseSeatModel(this.seatType),
                    /*jshint newcap: false */
                    seat = new seatClass(),
                    /*jshint newcap: true */
                    row = new this.rowView({
                        model: seat,
                        isRemovable: true,
                        course: this.course
                    }),
                    $tableBody = this.$el.find('tbody');

                row.render();
                $tableBody.append(row.el);

                // Add new seat to course product collection.
                this.course.get('products').add(seat);
            }
        });
    }
);
