define([
        'backbone',
        'backbone.super',
        'backbone.validation',
        'jquery',
        'jquery-cookie',
        'underscore',
        'moment',
        'utils/validation_patterns',
    ],
    function (Backbone,
              BackboneSuper,
              BackboneValidation,
              $,
              $cookie,
              _,
              moment
            ) {
        'use strict';

        _.extend(Backbone.Validation.messages, {
            required: gettext('This field is required'),
            number: gettext('This value must be a number'),
            date: gettext('This value must be a date')
        });
        _.extend(Backbone.Model.prototype, Backbone.Validation.mixin);

        return Backbone.Model.extend({
            urlRoot: '/api/v2/coupons/',

            defaults: {
                quantity: 1,
                stock_record_ids: [],
                code: ''
            },

            validation: {
                course_id: {
                    pattern: 'courseId',
                    msg: gettext('A valid course ID is required')
                },
                title: { required: true },
                client_username: { required: true },
                // seat_type is for validation only, stock_record_ids holds the values
                price: {
                    pattern: 'number',
                    required: function () {
                        return this.isEnrollmentCode();
                    }
                },
                seat_type: { required: true },
                quantity: { pattern: 'number' },
                benefit_value: {
                    pattern: 'number',
                    required: function () {
                        return this.isDiscountCode();
                    }
                },
                start_date: function (val) {
                    var startDate,
                        endDate;
                    if (_.isEmpty(val)) {
                        return Backbone.Validation.messages.required;
                    }
                    startDate = moment(new Date(val));
                    if (!startDate.isValid()) {
                        return Backbone.Validation.messages.date;
                    }
                    endDate = moment(this.get('end_date'));
                    if (endDate && startDate.isAfter(endDate)) {
                        return gettext('Must occur before end date');
                    }
                },
                end_date: function (val) {
                    var startDate,
                        endDate;
                    if (_.isEmpty(val)) {
                        return Backbone.Validation.messages.required;
                    }
                    endDate = moment(new Date(val));
                    if (!endDate.isValid()) {
                        return Backbone.Validation.messages.date;
                    }
                    startDate = moment(new Date(this.get('start_date')));
                    if (startDate && endDate.isBefore(startDate)) {
                        return gettext('Must occur after start date');
                    }
                }
            },

            isEnrollmentCode: function () {
                return this.get('code_type') === 'enrollment' ;
            },

            isDiscountCode: function () {
                return this.get('code_type') === 'discount' ;
            },

            initialize: function () {
                this.on('change:voucher_type', this.changeVoucherType, this);
            },

            /**
             * When user selects the 'Single use' limitation option set quantity to '1'.
             */
            changeVoucherType: function (model, value) {
                if (value === 'Single use') {
                    this.set('quantity', 1);
                }
            },

            save: function (options) {
                var data;

                _.defaults(options || (options = {}), {
                    type: 'POST',
                    // The API requires a CSRF token for all POST requests using session authentication.
                    headers: {'X-CSRFToken': $.cookie('ecommerce_csrftoken')},
                    contentType: 'application/json'
                });

                data = this.toJSON();
                data.start_date = moment.utc(this.get('start_date'));
                data.end_date = moment.utc(this.get('end_date'));

                // Enrolment code always gives 100% discount
                switch (this.get('code_type')) {
                case 'enrollment':
                    // this is the price paid for the code(s)
                    data.price = this.get('price');
                    data.benefit_type = 'Percentage';
                    data.benefit_value = 100;
                break;
                case 'discount':
                    data.price = 0;
                    data.benefit_type = this.get('benefit_type');
                    data.benefit_value = this.get('benefit_value');
                break;
                }

                options.data = JSON.stringify(data);
                return this._super(null, options);
            }
        });
    }
);
