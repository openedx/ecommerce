define([
        'underscore',
        'models/course_seats/professional_seat',
        'views/course_seat_form_fields/professional_course_seat_form_field_view'
    ],
    function (_,
              ProfessionalSeat,
              CourseSeatFormFieldView) {
        'use strict';

        var model, view;

        beforeEach(function () {
            model = new ProfessionalSeat();
            view = new CourseSeatFormFieldView({model: model}).render();
        });

        describe('getFieldValue', function () {
            it('should return a boolean if the name is id_verification_required', function () {
                var values = [true, false];

                // Sanity check for the default values
                expect(model.get('id_verification_required')).toEqual(false);
                expect(view.getFieldValue('id_verification_required')).toEqual(false);

                _.each(values, function (value) {
                    model.set('id_verification_required', value);

                    // Wait for backbone.stickit to update the DOM
                    setTimeout(function () {
                        expect(view.getFieldValue('id_verification_required')).toEqual(value);
                        done();
                    }, 1);

                });
            });

            it('should always return professional if the name is certificate_type', function () {
                expect(view.getFieldValue('certificate_type')).toEqual('professional');
            });
        });

    }
);
