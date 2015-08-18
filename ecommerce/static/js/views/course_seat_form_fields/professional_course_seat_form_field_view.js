define([
        'views/course_seat_form_fields/verified_course_seat_form_field_view',
        'text!templates/professional_course_seat_form_field.html'
    ],
    function (VerifiedCourseSeatFormFieldView,
              FieldTemplate) {
        'use strict';

        return VerifiedCourseSeatFormFieldView.extend({
            certificateType: 'professional',
            idVerificationRequired: false,
            seatType: 'professional',
            template: _.template(FieldTemplate)
        });
    }
);
