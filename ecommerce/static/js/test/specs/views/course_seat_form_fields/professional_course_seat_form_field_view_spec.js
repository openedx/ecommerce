define([
        'models/course_seats/professional_seat',
        'views/course_seat_form_fields/professional_course_seat_form_field_view'
    ],
    function (ProfessionalSeat,
              CourseSeatFormFieldView) {
        'use strict';

        var model, view;

        beforeEach(function () {
            model = new ProfessionalSeat();
            view = new CourseSeatFormFieldView({model: model}).render();
        });

        describe('professional course seat form field view', function () {
            describe('getFieldValue', function () {
                it('should return a boolean if the name is id_verification_required', function () {
                    // NOTE (CCB): Ideally _.each should be used here to loop over an array of Boolean values.
                    // However, the tests fail when that implementation is used, hence the repeated code.
                    model.set('id_verification_required', false);
                    expect(model.get('id_verification_required')).toEqual(false);
                    expect(view.getFieldValue('id_verification_required')).toEqual(false);

                    model.set('id_verification_required', true);
                    expect(model.get('id_verification_required')).toEqual(true);
                    expect(view.getFieldValue('id_verification_required')).toEqual(true);
                });

                // NOTE (CCB): This test is flaky (hence it being skipped).
                // Occasionally, calls to the parent class fail.
                xit('should always return professional if the name is certificate_type', function () {
                    expect(view.getFieldValue('certificate_type')).toEqual('professional');
                });
            });
        });
    }
);
