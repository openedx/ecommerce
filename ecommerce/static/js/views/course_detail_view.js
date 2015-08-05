define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'moment',
        'text!templates/course_detail.html',
        'text!templates/_course_seat.html'
    ],
    function ($,
              Backbone,
              _,
              _s,
              moment,
              CourseDetailTemplate,
              CourseSeatTemplate) {
        'use strict';

        return Backbone.View.extend({
            className: 'course-detail-view',

            initialize: function () {
                this.listenTo(this.model, 'change', this.render);
            },

            getSeats: function () {
                // Returns an array of seats sorted for display
                var seats,
                    sortObj = _.invert(_.object(_.pairs([
                        'honor', 'verified', 'no-id-professional', 'professional', 'credit'
                    ])));

                seats = _.values(this.model.getSeats());
                seats = _.sortBy(seats, function (seat) {
                    return sortObj[seat.get('certificate_type')]
                });

                return seats;
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
                    $seatHolder = $('.course-seats', this.$el);

                _.each(this.getSeats(), function (seat) {
                    html += _.template(CourseSeatTemplate)({seat: seat, moment: moment});
                });

                $seatHolder.html(html);
            }
        });
    }
);
