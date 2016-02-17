define([
        'backbone',
        'backbone.super',
        'backbone.validation',
        'jquery',
        'jquery-cookie',
        'underscore',
        'moment',
        'utils/validation_patterns'
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
                code: '',
                price: 0,
                category: 4,
                sub_category: 'default'
            },

            validation: {
                course_id: {
                    pattern: 'courseId',
                    msg: gettext('A valid course ID is required')
                },
                title: { required: true },
                client: { required: true },
                // seat_type is for validation only, stock_record_ids holds the values
                seat_type: { required: true },
                quantity: { pattern: 'number' },
                price: { pattern: 'number' },
                category: { required: true },
                sub_category: { required: true },
                benefit_value: {
                    pattern: 'number',
                    required: function () {
                        return this.get('coupon_type') === 'discount';
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

            initialize: function () {
                this.on('change:voucher_type', this.changeVoucherType, this);
                this.on('change:seats', this.updateSeatData);
                this.on('change:vouchers', this.updateVoucherData);
            },

            /**
             * When user selects the 'Single use' limitation option set quantity to '1'.
             */
            changeVoucherType: function (model, value) {
                if (value === 'Single use') {
                    this.set('quantity', 1);
                }
            },

            updateSeatData: function () {
                var seat_data = this.get('seats')[0].attribute_values,
                    seat_type = _.findWhere(seat_data, {'name': 'certificate_type'}),
                    course_id = _.findWhere(seat_data, {'name': 'course_key'});
                this.set('seat_type', seat_type ? seat_type.value : '');
                this.set('course_id', course_id ? course_id.value : '');
            },

            updateVoucherData: function () {
                var vouchers = this.get('vouchers'),
                    voucher = vouchers[0],
                    code_count = _.findWhere(voucher, {'code': voucher.code});
                this.set('start_date', voucher.start_datetime);
                this.set('end_date', voucher.end_datetime);
                this.set('voucher_type', voucher.usage);
                if (this.get('coupon_type') === 'Discount code') {
                    this.set('benefit_type', voucher.benefit[0]);
                    this.set('benefit_value', voucher.benefit[1]);
                }

                if (code_count > 1 || _.size(vouchers) === 1) {
                    this.set('code', voucher.code);
                }
            },

            save: function (options) {
                var data;

                _.defaults(options || (options = {}), {
                    // The API requires a CSRF token for all POST requests using session authentication.
                    headers: {'X-CSRFToken': $.cookie('ecommerce_csrftoken')},
                    contentType: 'application/json'
                });

                data = this.toJSON();
                data.client_username = this.get('client');
                data.start_date = moment.utc(this.get('start_date'));
                data.end_date = moment.utc(this.get('end_date'));
                data.price = this.get('price');
                data.category = this.get('category');
                data.sub_category = this.get('sub_category');

                // Enrollment code always gives 100% discount
                switch (this.get('coupon_type')) {
                case 'enrollment':
                    // this is the price paid for the code(s)
                    data.benefit_type = 'Percentage';
                    data.benefit_value = 100;
                break;
                case 'discount':
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
