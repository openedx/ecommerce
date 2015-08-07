define([
        'views/course_seat_form_fields/course_seat_form_field_view',
        'text!templates/audit_course_seat_form_field.html'
    ],
    function (CourseSeatFormFieldView,
              FieldTemplate) {
        'use strict';

        return CourseSeatFormFieldView.extend({
            certificateType: null,
            idVerificationRequired: false,
            seatType: 'audit',
            template: _.template(FieldTemplate)
        });
    }
);
