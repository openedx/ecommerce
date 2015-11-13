// jscs:disable requireCapitalizedConstructors

define([
        'backbone',
        'backbone.relational',
        'backbone.super',
        'backbone.validation',
        'jquery',
        'jquery-cookie',
        'underscore',
        'moment',
        'models/partner_model',
        'models/course_model'
    ],
    function (Backbone,
              BackboneRelational,
              BackboneSuper,
              BackboneValidation,
              $,
              $cookie,
              _,
              moment,
              Partner,
              Course) {
        'use strict';

        _.extend(Backbone.Model.prototype, Backbone.Validation.mixin);

        _.extend(Backbone.Validation.patterns, {
            courseId: /[^/+]+(\/|\+)[^/+]+(\/|\+)[^/]+/
        });

        _.extend(Backbone.Validation.messages, {
            courseId: gettext('The course ID is invalid.')
        });

        return Backbone.RelationalModel.extend({
            urlRoot: '/api/v2/enrollment_codes/',

            defaults: {
            },

            validation: {
                course_id: {
                    pattern: 'courseId'
                },
                client_name: {
                    required: true
                },
                total_code_count: {
                    required: true
                },
                total_cost: {
                    required: true
                },
                start_date: function (val) {
                    if (_.isEmpty(val)) {
                        return gettext('Start date is required')
                    }
                    var isValid = moment(val).isValid();
                    if (!isValid) {
                        return gettext('Start date is invalid')
                    }
                    var endDate = this.get('end_date')
                    var isBefore = moment(val).isBefore(endDate);
                    if (endDate && !isBefore) {
                        return gettext('Must occur before end date')
                    }
                },
                end_date: function (val) {
                    if (_.isEmpty(val)) {
                        return gettext('End date is required')
                    }
                    var isValid = moment(val).isValid();
                    if (!isValid) {
                        return gettext('End date is invalid')
                    }
                    var startDate = this.get('start_date')
                    var isAfter = moment(val).isAfter(startDate);
                    if (startDate && !isAfter) {
                        return gettext('Must occur after start date')
                    }
                }
            },

            labels: {
            },

            relations: [
                {
                    type: Backbone.HasOne,
                    key: 'course',
                    relatedModel: Course,
                    includeInJSON: false
                },
                {
                    type: Backbone.HasOne,
                    key: 'partner',
                    relatedModel: Partner,
                    includeInJSON: false
                }
            ],

            initialize: function () {
                this.on('change:course_id', this.fillFromCourse, this);
                this.on('change:seat_type', this.fillFromSeatType, this);
                this.on('change:total_code_count', this.calculateTotalCost, this);
            },

            fillFromCourse: function (model, value, options) {
                this.set('course', value);

                var valid = this.isValid('course_id');
                if (!valid) {
                    this.emptyCourseFields();
                    return;
                }
                var self = this
                var promise = this.getAsync('course', {data: {include_products: true}});
                promise.then(function () {
                    var course = self.get('course')
                    self.set('course_name', course.get('name'))
                    var seatTypes = _.map(course.seats(), function(val) {
                        return {
                            value: val.get('certificate_type'),
                            label: val.getSeatTypeDisplayName()
                        };
                    })
                    self.set('seatTypes', seatTypes)

                    // triggers update for seat_type selectOptions
                    self.set('seat_type', seatTypes[0].value);
                })
                promise.fail(function() {
                    self.emptyCourseFields()
                })
            },

            emptyCourseFields: function () {
                this.set('course_name', '')
                this.set('partner_name', '')
            },

            fillFromSeatType: function (model, value, options) {
                // get partner from stock records
                var seat = this.get('course').get('products')
                    .findWhere({certificate_type: value})
                var stockrecord = seat.get('stockrecords')[0]

                var self = this
                this.set('stockrecord', stockrecord)
                this.set('partner', stockrecord.partner)
                this.getAsync('partner').then(function () {
                    var partner = self.get('partner')
                    self.set('partner_name', partner.get('name'))
                })

                this.set('full_seat_price', seat.get('price'))
                this.set('code_seat_price', seat.get('price'))
            },

            calculateTotalCost: function (model, value, options) {
                var codePrice = this.get('code_seat_price')
                var codeCount = this.get('total_code_count')
                this.set('total_cost', codePrice * codeCount)
            },

            save: function (options) {
                _.defaults(options || (options = {}), {
                    type: 'POST',
                    // The API requires a CSRF token for all POST requests using session authentication.
                    headers: {'X-CSRFToken': $.cookie('ecommerce_csrftoken')},
                    contentType: 'application/json'
                });

                var data = {
                    client: this.get('client_name'),
                    stock_records: [this.get('stockrecord').id],
                    quantity: this.get('total_code_count'),
                    start_date: this.get('start_date'),
                    end_date: this.get('end_date'),
                    type: this.get('code_type'),
                    price: this.get('total_cost')
                }
                options.data = JSON.stringify(data);
                return this._super(null, options);
            }
        });
    }
);
