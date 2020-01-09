define([
    'underscore',
    'views/course_seat_form_fields/course_seat_form_field_view',
    'text!templates/honor_course_seat_form_field.html'
],
    function(_,
             CourseSeatFormFieldView,
             FieldTemplate) {
        'use strict';

        return CourseSeatFormFieldView.extend({
            certificateType: 'honor',
            idVerificationRequired: false,
            seatType: 'honor',
            template: _.template(FieldTemplate)
        });
    }
);
