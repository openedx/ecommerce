define([
        'backbone',
        'backbone.super',
        'backbone.validation',
        'jquery',
        'jquery-cookie',
        'underscore',
        'moment',
        'collections/category_collection',
        'models/category',
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
            required: gettext('This field is required.'),
            number: gettext('This value must be a number.'),
            date: gettext('This value must be a date.'),
            seat_types: gettext('At least one seat type must be selected.'),
        });
        _.extend(Backbone.Model.prototype, Backbone.Validation.mixin);

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/coupons/',

            defaults: {
                id: null,
                quantity: 1,
                stock_record_ids: [],
                code: '',
                price: 0,
                total_value: 0,
                max_uses: 1,
                seats: [],
                course_seats: [],
                course_seat_types: []
            },

            validation: {
                category: {required: true},
                course_id: {
                    pattern: 'courseId',
                    msg: gettext('A valid course ID is required'),
                    required: function () {
                        return this.get('catalog_type') === 'Single course';
                    }
                },
                title: {required: true},
                client: {required: true},
                // seat_type is for validation only, stock_record_ids holds the values
                seat_type: {
                    required: function () {
                        return this.get('catalog_type') === 'Single course';
                    }
                },
                quantity: {pattern: 'number'},
                price: {pattern: 'number'},
                benefit_value: {
                    pattern: 'number',
                    required: function () {
                        return this.get('coupon_type') === 'Discount code';
                    }
                },
                code: {
                    required: false,
                    rangeLength: [8, 16],
                    msg: gettext('Code field must be empty or between 8 and 16 characters')
                },
                catalog_query: {
                    required: function () {
                        return this.get('catalog_type') === 'Multiple courses';
                    }
                },
                course_seat_types: function (val) {
                    if (this.get('catalog_type') === 'Multiple courses' && val.length === 0) {
                        return Backbone.Validation.messages.seat_types;
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
                this.on('change:vouchers', this.updateVoucherData);
                this.on('change:seats', this.updateSeatData);
                this.on('change:quantity', this.updateTotalValue(this.getSeatPrice));
            },

            /**
             * When user selects the 'Single use' limitation option set quantity to '1'.
             */
            changeVoucherType: function (model, value) {
                if (value === 'Single use') {
                    this.set('quantity', 1);
                }
            },

            getSeatPrice: function () {
                var seats = this.get('seats');
                return seats[0] ? seats[0].price : '';
            },

            updateTotalValue: function (seat_price) {
                this.set('total_value', this.get('quantity') * seat_price);
            },

            getCertificateType: function(seat_data) {
                var seat_type = _.findWhere(seat_data, {'name': 'certificate_type'});
                return seat_type ? seat_type.value : '';
            },

            getCourseID: function(seat_data) {
                var course_id = _.findWhere(seat_data, {'name': 'course_key'});
                return course_id ? course_id.value : '';
            },

            updateSeatData: function () {
                var seat_data,
                    seats = this.get('seats');

                this.set('catalog_type', this.has('catalog_query') ? 'Multiple courses': 'Single course');

                if (this.get('catalog_type') === 'Single course') {
                    if (seats[0]) {
                        seat_data = seats[0].attribute_values;

                        this.set('seat_type', this.getCertificateType(seat_data));
                        this.set('course_id', this.getCourseID(seat_data));
                        this.updateTotalValue(this.getSeatPrice());
                    }
                }
            },

            updateVoucherData: function () {
                var vouchers = this.get('vouchers'),
                    voucher = vouchers[0],
                    code_count = _.findWhere(voucher, {'code': voucher.code});
                this.set('start_date', voucher.start_datetime);
                this.set('end_date', voucher.end_datetime);
                this.set('voucher_type', voucher.usage);
                this.set('quantity', _.size(vouchers));
                this.updateTotalValue(this.getSeatPrice());
                if (this.get('coupon_type') === 'Discount code') {
                    this.set('benefit_type', voucher.benefit.type);
                    this.set('benefit_value', voucher.benefit.value);
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
                data.category_ids = [ this.get('category') ];

                // Enrollment code always gives 100% discount
                switch (this.get('coupon_type')) {
                    case 'Enrollment code':
                        // this is the price paid for the code(s)
                        data.benefit_type = 'Percentage';
                        data.benefit_value = 100;
                        break;
                    case 'Discount code':
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
