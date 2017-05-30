define([
    'backbone',
    'backbone.super',
    'backbone.validation',
    'jquery',
    'js-cookie',
    'underscore',
    'underscore.string',
    'utils/utils',
    'moment',
    'backbone.relational'
],
    function(Backbone,
              BackboneSuper,
              BackboneValidation,
              $,
              Cookies,
              _,
              _s,
              Utils,
              moment) {
        'use strict';

        /* eslint-env es6: true */
        var CATALOG_TYPES = {
            single_course: 'Single course',
            multiple_courses: 'Multiple courses',
            catalog: 'Catalog',
            program: 'Program'
        };

        _.extend(Backbone.Validation.messages, {
            required: gettext('This field is required.'),
            number: gettext('This value must be a number.'),
            date: gettext('This value must be a date.'),
            seat_types: gettext('At least one seat type must be selected.')
        });
        _.extend(Backbone.Model.prototype, Backbone.Validation.mixin);

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/coupons/',

            defaults: {
                category: {id: 3, name: 'Affiliate Promotion'},
                code: '',
                course_seats: [],
                course_seat_types: [],
                id: null,
                max_uses: 1,
                price: 0,
                quantity: 1,
                seats: [],
                stock_record_ids: [],
                total_value: 0
            },

            catalogTypes: CATALOG_TYPES,

            validation: {
                benefit_value: {
                    pattern: 'number',
                    required: function() {
                        return this.get('coupon_type') === 'Discount code';
                    }
                },
                catalog_query: {
                    required: function() {
                        return this.get('catalog_type') === CATALOG_TYPES.multiple_courses;
                    }
                },
                course_catalog: {
                    required: function() {
                        return this.get('catalog_type') === CATALOG_TYPES.catalog;
                    }
                },
                category: {required: true},
                client: {required: true},
                code: {
                    pattern: /^[a-zA-Z0-9]+$/,
                    required: false,
                    rangeLength: [1, 16],
                    msg: gettext('This field must be empty or contain 1-16 alphanumeric characters.')
                },
                course_id: {
                    pattern: 'courseId',
                    msg: gettext('A valid course ID is required'),
                    required: function() {
                        return this.get('catalog_type') === CATALOG_TYPES.single_course;
                    }
                },
                course_seat_types: function(val) {
                    // add validation only for dynamic coupons, e.g. dynamic query coupon or catalog coupon
                    var dynamicCoupons = [CATALOG_TYPES.multiple_courses, CATALOG_TYPES.catalog];
                    if (dynamicCoupons.indexOf(this.get('catalog_type')) !== -1 && val.length === 0) {
                        return Backbone.Validation.messages.seat_types;
                    }
                    return undefined;
                },
                email_domains: function(val) {
                    var invalidDomain;

                    if (!_.isEmpty(val)) {
                        invalidDomain = Utils.validateDomains(val);

                        if (invalidDomain) {
                            return _s.sprintf(gettext('Email domain {%s} is invalid.'), invalidDomain);
                        }
                    }
                    return undefined;
                },
                enterprise_customer: {required: false},
                end_date: function(val) {
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

                    return undefined;
                },
                invoice_discount_value: {
                    pattern: 'number',
                    required: function() {
                        return this.get('invoice_type') === 'Postpaid';
                    }
                },
                invoice_number: {
                    required: function() {
                        return this.isPrepaidInvoiceType();
                    }
                },
                invoice_payment_date: {
                    required: function() {
                        return this.isPrepaidInvoiceType();
                    }
                },
                invoice_type: {required: true},
                max_uses: function(val) {
                    var numberPattern = new RegExp('[0-9]+');
                    if (val === '') {
                        this.unset('max_uses');
                    }
                    if (val && !numberPattern.test(val)) {
                        return Backbone.Validation.messages.number;
                    } else if (val && val < 2 && this.get('voucher_type') === 'Multi-use') {
                        return gettext('Max uses for multi-use coupons must be higher than 2.');
                    }

                    return undefined;
                },
                price: {
                    pattern: 'number',
                    required: function() {
                        return this.isPrepaidInvoiceType();
                    }
                },
                program_uuid: {
                    msg: gettext('A valid Program UUID is required.'),
                    required: function() {
                        return this.get('catalog_type') === CATALOG_TYPES.program;
                    }
                },
                quantity: {pattern: 'number'},
                // seat_type is for validation only, stock_record_ids holds the values
                seat_type: {
                    required: function() {
                        return this.get('catalog_type') === CATALOG_TYPES.single_course;
                    }
                },
                start_date: function(val) {
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

                    return undefined;
                },
                title: {required: true}
            },

            url: function() {
                var url = this._super();

                // Ensure the URL always ends with a trailing slash
                url += _s.endsWith(url, '/') ? '' : '/';

                return url;
            },

            initialize: function() {
                this.on('change:seats', this.updateSeatData);
                this.on('change:quantity', this.updateTotalValue(this.getSeatPrice));
                this.on('change:payment_information', this.updatePaymentInformation);
            },

            isPrepaidInvoiceType: function() {
                return this.get('invoice_type') === 'Prepaid';
            },

            getSeatPrice: function() {
                var seats = this.get('seats');
                return seats[0] ? seats[0].price : '';
            },

            updateTotalValue: function(seatPrice) {
                this.set('total_value', this.get('quantity') * seatPrice);
            },

            getCertificateType: function(seatData) {
                var seatType = _.findWhere(seatData, {name: 'certificate_type'});
                return seatType ? seatType.value : '';
            },

            getCourseID: function(seatData) {
                var courseId = _.findWhere(seatData, {name: 'course_key'});
                return courseId ? courseId.value : '';
            },

            updateSeatData: function() {
                var seatData,
                    seats = this.get('seats'),
                    catalogId,
                    catalogType;

                catalogId = '';
                if (this.has('course_catalog') && this.get('course_catalog') !== null) {
                    if (typeof this.get('course_catalog') === 'number') {
                        catalogId = this.get('course_catalog');
                    }
                }

                if (this.has('catalog_query') && this.get('catalog_query') !== '') {
                    catalogType = this.catalogTypes.multiple_courses;
                } else if (catalogId !== '') {
                    catalogType = this.catalogTypes.catalog;
                } else if (this.has('program_uuid')) {
                    catalogType = this.catalogTypes.program;
                } else {
                    catalogType = this.catalogTypes.single_course;
                }
                this.set('catalog_type', catalogType);

                if (this.get('catalog_type') === this.catalogTypes.single_course) {
                    if (seats !== null && seats[0]) {
                        seatData = seats[0].attribute_values;

                        this.set('seat_type', this.getCertificateType(seatData));
                        this.set('course_id', this.getCourseID(seatData));
                        this.updateTotalValue(this.getSeatPrice());
                    }
                }
            },

            updatePaymentInformation: function() {
                var paymentInformation = this.get('payment_information'),
                    invoice = paymentInformation.Invoice,
                    taxDeducted = invoice.tax_deducted_source ? 'Yes' : 'No';
                this.set({
                    invoice_type: invoice.type,
                    invoice_discount_type: invoice.discount_type,
                    invoice_discount_value: invoice.discount_value,
                    invoice_number: invoice.number,
                    invoice_payment_date: invoice.payment_date,
                    tax_deducted_source: invoice.tax_deducted_source,
                    tax_deduction: taxDeducted
                });
            },

            save: function(attributes, options) {
                /* eslint no-param-reassign: 2 */

                // Remove all saved models from store, which prevents Duplicate id errors
                Backbone.Relational.store.reset();

                _.defaults(options || (options = {}), {
                    // The API requires a CSRF token for all POST requests using session authentication.
                    headers: {'X-CSRFToken': Cookies.get('ecommerce_csrftoken')},
                    contentType: 'application/json'
                });

                if (!options.patch) {
                    this.set('start_datetime', moment.utc(this.get('start_date')));
                    this.set('end_datetime', moment.utc(this.get('end_date')));

                    if (this.get('coupon_type') === 'Enrollment code') {
                        this.set('benefit_type', 'Percentage');
                        this.set('benefit_value', 100);
                    }

                    options.data = JSON.stringify(this.toJSON());
                } else {
                    if (_.has(attributes, 'start_date')) {
                        attributes.start_datetime = moment.utc(attributes.start_date);
                    }

                    if (_.has(attributes, 'end_date')) {
                        attributes.end_datetime = moment.utc(attributes.end_date);
                    }

                    if (_.has(attributes, 'title')) {
                        attributes.name = attributes.title;
                    }
                }

                return this._super(attributes, options);
                /* eslint no-param-reassign: 0 */
            }
        });
    }
);
