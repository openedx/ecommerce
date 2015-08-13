define([
        'models/course_seats/verified_seat',
        'views/course_seat_form_fields/verified_course_seat_form_field_view'
    ],
    function (VerifiedSeat,
              VerifiedCourseSeatFormFieldView) {
        'use strict';

        var model, view;

        beforeEach(function () {
            model = new VerifiedSeat();
            view = new VerifiedCourseSeatFormFieldView({model: model}).render();
        });

        describe('getData', function () {
            it('should return the data from the DOM/model', function () {
                var data = {
                    certificate_type: 'verified',
                    id_verification_required: 'true',
                    price: '100',
                    expires: ''
                };

                expect(view.getData()).toEqual(data);
            });
        });
    }
);
