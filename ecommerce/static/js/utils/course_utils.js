define([
        'underscore',
        'models/course_seats/audit_seat',
        'models/course_seats/course_seat',
        'models/course_seats/honor_seat',
        'models/course_seats/professional_seat',
        'models/course_seats/verified_seat'
    ],
    function (_,
              AuditSeat,
              CourseSeat,
              HonorSeat,
              ProfessionalSeat,
              VerifiedSeat) {
        'use strict';

        return {
            seatSortObj: _.invert(_.object(_.pairs([
                'audit', 'honor', 'verified', 'no-id-professional', 'professional', 'credit'
            ]))),

            /**
             * Returns a mapping of seat types to CourseSeat classes.
             *
             * All classes included in the map extend CourseSeat.
             *
             * @returns {CourseSeat[]}
             */
            getSeatModelMap: _.memoize(function () {
                return _.indexBy([AuditSeat, HonorSeat, ProfessionalSeat, VerifiedSeat], 'seatType');
            }),

            /**
             * Returns a CourseSeat class corresponding to the seat type.
             *
             * @param {String} seatType
             * @returns {CourseSeat} - CourseSeat subclass, or CourseSeat if seatType is not mapped to a specific class.
             */
            getCourseSeatModel: function (seatType) {
                return this.getSeatModelMap()[seatType] || CourseSeat;
            },

            /**
             * Returns the seat type for a given model.
             *
             * @param {Backbone.Model|Object} seat
             * @returns {String|null}
             */
            getSeatType: function (seat) {
                var seatType = seat.seatType;

                if (!seatType) {
                    // Fall back to using certificate type
                    switch (seat.get('certificate_type') || seat.certificate_type) {
                        case 'verified':
                            seatType = 'verified';
                            break;
                        case 'credit':
                            seatType = 'credit';
                            break;
                        case 'professional':
                        case 'no-id-professional':
                            seatType = 'professional';
                            break;
                        case 'honor':
                            seatType = 'honor';
                            break;
                        default:
                            seatType = 'audit';
                            break;
                    }
                }

                return seatType;
            },


            /**
             * Returns an array of CourseSeats, ordered as they should be displayed.
             * @param {CourseSeat[]} seats
             * @returns {CourseSeat[]}
             */
            orderSeatsForDisplay: function (seats) {
                return _.sortBy(seats, function (seat) {
                    return this.seatSortObj[seat.getSeatType()];
                }, this);
            },

            orderSeatTypesForDisplay: function(seatTypes){
                return _.sortBy(seatTypes, function (seatType) {
                    return this.seatSortObj[seatType];
                }, this);
            }
        }
    }
);