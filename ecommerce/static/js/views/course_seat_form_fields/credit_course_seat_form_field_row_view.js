define([
        'backbone',
        'backbone.stickit',
        'text!templates/credit_course_seat_form_field_row.html'
    ],
    function (Backbone,
              BackboneStickit,
              CreditSeatTableRowTemplate) {
        'use strict';

        return Backbone.View.extend({
            tagName: 'tr',
            className: 'course-seat',
            template: _.template(CreditSeatTableRowTemplate),

            events: {
                'click .remove-seat': 'removeSeatTableRow'
            },

            bindings: {
                'input[name=credit_provider]': {
                    observe: 'credit_provider',
                    setOptions: {
                        validate: true
                    }
                },
                'input[name=price]': {
                    observe: 'price',
                    setOptions: {
                        validate: true
                    }
                },
                'input[name=credit_hours]': {
                    observe: 'credit_hours',
                    setOptions: {
                        validate: true
                    }
                },
                'input[name=expires]': {
                    observe: 'expires',
                    setOptions: {
                        validate: true
                    }
                }
            },

            initialize: function (options) {
                this.course = options.course;
                this.isRemovable = options.isRemovable;
            },

            render: function () {
                var context = _.extend({}, this.model.attributes, {isRemovable: this.isRemovable});

                this.$el.html(this.template(context));
                this.stickit();

                return this;
            },

            /**
             * Removes the selected row from the seat table.
             */
            removeSeatTableRow: function () {
                // Remove deleted seat from course product collection.
                this.course.get('products').remove(this.model);
                this.remove();
            }
        });
    }
);
