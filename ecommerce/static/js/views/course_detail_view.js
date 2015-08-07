define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'moment',
        'text!templates/course_detail.html',
        'text!templates/_course_seat.html',
        'utils/course_utils'
    ],
    function ($,
              Backbone,
              _,
              _s,
              moment,
              CourseDetailTemplate,
              CourseSeatTemplate,
              CourseUtils) {
        'use strict';

        return Backbone.View.extend({
            className: 'course-detail-view',

            initialize: function () {
                this.listenTo(this.model, 'change', this.render);
            },

            render: function () {
                var html,
                    verificationDeadline = this.model.get('verification_deadline'),
                    templateData;

                templateData = {
                    course: this.model.attributes,
                    courseType: _s.capitalize(this.model.get('type')),
                    verificationDeadline: verificationDeadline ? moment.utc(verificationDeadline).format('lll z') : null
                };

                html = _.template(CourseDetailTemplate)(templateData);
                this.$el.html(html);

                this.renderSeats();

                return this;
            },

            renderSeats: function () {
                var html = '',
                    seats = CourseUtils.orderSeatsForDisplay(this.model.seats()),
                    $seatHolder = $('.course-seats', this.$el);

                _.each(seats, function (seat) {
                    html += _.template(CourseSeatTemplate)({seat: seat, moment: moment});
                });

                $seatHolder.html(html);
            }
        });
    }
);
