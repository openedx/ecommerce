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
            tagName: 'div',
            className: '.course-detail-view',

            initialize: function () {
                var self = this;

                _.bindAll(this, 'render');

                this.model.bind('change', this.render);
                this.model.bind('change:products', this.renderSeats);

                this.model.fetch();

            },

            getSeats: function () {
                // Returns an array of seats sorted for display
                var seats,
                    sortObj = _.invert(_.object(_.pairs([
                        'honor', 'verified', 'no-id-professional', 'professional', 'credit'
                    ])));

                seats = _.sortBy(this.model.getSeats(), function (seat) {
                    return sortObj[seat.get('certificate_type')]
                });

                return seats;
            },

            render: function () {
                var html, templateData;
                document.title = this.model.get('name') + ' - ' + gettext('View Course');

                templateData = {
                    course: this.model.attributes,
                    courseType: _s.capitalize(this.model.get('type'))
                };

                html = _.template(CourseDetailTemplate)(templateData);
                this.$el.html(html);
                return this;
            },

            renderSeats: function () {
                var html = '',
                    $seatHolder = $('.course-seats', this.$el);

                this.getSeats().forEach(function (seat) {
                    html += _.template(CourseSeatTemplate)({seat: seat, moment: moment});
                });

                $seatHolder.append(html);

                return this;
            }
        });
    }
);
