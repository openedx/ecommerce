define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'moment',
        'models/course_model',
        'text!templates/course_detail.html',
        'text!templates/_course_seat.html'
    ],
    function ($,
              Backbone,
              _,
              _s,
              moment,
              CourseModel,
              CourseDetailTemplate,
              CourseSeatTemplate) {
        'use strict';

        return Backbone.View.extend({
            el: '.course-detail-view',

            initialize: function () {
                var self = this,
                    course_id = self.$el.data('course-id');

                this.course = new CourseModel({id: course_id});
                this.course.fetch({
                    success: function (course) {
                        self.render();
                        course.getProducts().done(function () {
                            self.renderSeats();
                        });
                    }
                });
            },

            getSeats: function () {
                // Returns an array of seats sorted for display
                var seats,
                    sortObj = _.invert(_.object(_.pairs([
                        'honor', 'verified', 'no-id-professional', 'professional', 'credit'
                    ])));

                seats = _.sortBy(this.course.getSeats(), function (seat) {
                    return sortObj[seat.get('certificate_type')]
                });

                return seats;
            },

            render: function () {
                var html, templateData;
                document.title = this.course.get('name') + ' - ' + gettext('View Course');

                templateData = {
                    course: this.course.attributes,
                    courseType: _s.capitalize(this.course.get('type'))
                };

                html = _.template(CourseDetailTemplate)(templateData);
                this.$el.html(html)
            },

            renderSeats: function () {
                var html = '',
                    $seatHolder = $('.course-seats', this.$el);

                this.getSeats().forEach(function (seat) {
                    html += _.template(CourseSeatTemplate)({seat: seat, moment: moment});
                });

                $seatHolder.append(html);
            }
        });
    }
);
