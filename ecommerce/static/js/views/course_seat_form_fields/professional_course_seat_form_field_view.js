define([
        'underscore.string',
        'views/course_seat_form_fields/verified_course_seat_form_field_view',
        'text!templates/professional_course_seat_form_field.html'
    ],
    function (_s,
              VerifiedCourseSeatFormFieldView,
              FieldTemplate) {
        'use strict';

        return VerifiedCourseSeatFormFieldView.extend({
            certificateType: 'professional',
            seatType: 'professional',
            template: _.template(FieldTemplate),

            initialize: function () {
                this._super();
                this.listenTo(this.model, 'change:id_verification_required', this.verificationChanged);
            },

            render: function () {
                this._super();
                this.verificationChanged();
                return this;
            },

            getFieldValue: function (name) {
                var value;

                if (name === 'id_verification_required') {
                    value = this.$('input[name=id_verification_required]:checked').val();
                    value = _s.toBoolean(value);
                } else {
                    value = this._super(name);
                }

                return value;
            },

            verificationChanged: function () {
                var idVerificationRequired = this.model.get('id_verification_required'),
                    $expires = this.$el.find('.form-group.verification-close');

                $expires.toggle(idVerificationRequired);
            }
        });
    }
);
