define([
    'underscore',
    'views/course_seat_form_fields/course_seat_form_field_view',
    'text!templates/verified_course_seat_form_field.html'
],
    function(_,
             CourseSeatFormFieldView,
             FieldTemplate) {
        'use strict';

        return CourseSeatFormFieldView.extend({
            certificateType: 'verified',
            idVerificationRequired: true,
            seatType: 'verified',
            template: _.template(FieldTemplate)
        });
    }
);
