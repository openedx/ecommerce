define([
        'underscore',
        'utils/course_utils',
        'models/course_seats/audit_seat',
        'models/course_seats/course_seat',
        'models/course_seats/honor_seat',
        'models/course_seats/professional_seat',
        'models/course_seats/verified_seat'
    ],
    function (_,
              CourseUtils,
              AuditSeat,
              CourseSeat,
              HonorSeat,
              ProfessionalSeat,
              VerifiedSeat) {
        'use strict';

        describe('CourseUtils', function () {
            describe('getCourseSeatModel', function () {
                it('should return the CourseSeat child class corresponding to a seat type', function () {
                    expect(CourseUtils.getCourseSeatModel('audit')).toEqual(AuditSeat);
                    expect(CourseUtils.getCourseSeatModel('honor')).toEqual(HonorSeat);
                    expect(CourseUtils.getCourseSeatModel('professional')).toEqual(ProfessionalSeat);
                    expect(CourseUtils.getCourseSeatModel('verified')).toEqual(VerifiedSeat);
                });

                it('should return CourseSeat if the seat type is unknown', function () {
                    expect(CourseUtils.getCourseSeatModel(null)).toEqual(CourseSeat);
                });
            });

            describe('orderSeatTypesForDisplay', function () {
                it('should return a list ordered seat types', function () {
                    var data = [
                        ['audit', 'professional', 'credit'],
                        ['audit', 'honor', 'verified', 'professional', 'credit']
                    ];

                    _.each(data, function (expected) {
                        expect(CourseUtils.orderSeatTypesForDisplay(_.shuffle(expected))).toEqual(expected);
                    });
                });
            });

            describe('filterSeats', function () {
                it('should filter CourseSeats of the requested type', function () {
                    var honor = new HonorSeat(),
                        verified = new VerifiedSeat(),
                        professional = new ProfessionalSeat(),
                        expected = [
                            {
                                input: [honor, verified, professional],
                                output: {
                                    filtered: [verified],
                                    residual: [honor, professional]
                                }
                            },
                            {
                                input: [honor, verified, verified, professional],
                                output: {
                                    filtered: [verified, verified],
                                    residual: [honor, professional]
                                }
                            }
                        ];

                    _.each(expected, function (expected) {
                        expect(CourseUtils.filterSeats(expected.input, 'verified')).toEqual(expected.output);
                    });
                });
            });
        });
    }
);
