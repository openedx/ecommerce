define([
        'models/course_seats/course_seat',
        'views/course_seat_form_fields/course_seat_form_field_view'
    ],
    function (CourseSeat,
              CourseSeatFormFieldView) {
        'use strict';

        var model, view;

        beforeEach(function () {
            model = new CourseSeat();
            view = new CourseSeatFormFieldView({model: model});
        });

        describe('course seat form field view', function () {
            describe('cleanIdVerificationRequired', function () {
                it('should always return a boolean', function () {
                    expect(view.cleanIdVerificationRequired('false')).toEqual(false);
                    expect(view.cleanIdVerificationRequired('true')).toEqual(true);
                });
            });
        });
    }
);
