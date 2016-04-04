// jscs:disable requireCapitalizedConstructors

define([
        'jquery',
        'backbone',
        'backbone.super',
        'backbone.validation',
        'backbone.stickit',
        'ecommerce',
        'underscore',
        'underscore.string',
        'utils/utils',
        'text!templates/coupon_form.html',
        'models/course_model',
        'views/form_view',
    ],
    function ($,
              Backbone,
              BackboneSuper,
              BackboneValidation,
              BackboneStickit,
              ecommerce,
              _,
              _s,
              Utils,
              CouponFormTemplate,
              Course,
              FormView) {
        'use strict';

        return FormView.extend({
            tagName: 'form',

            className: 'coupon-form-view',

            template: _.template(CouponFormTemplate),

            seatTypes: [],

            codeTypes: [
                {
                    value: 'enrollment',
                    label: gettext('Enrollment Code')
                },
                {
                    value: 'discount',
                    label: gettext('Discount Code')
                }
            ],

            voucherTypes: [
                {
                    value: 'Single use',
                    label: gettext('Can be used once by one customer')
                },
                {
                    value: 'Once per customer',
                    label: gettext('Can be used once by multiple customers')
                }
            ],

            bindings: {
                'select[name=category]': {
                    observe: 'category',
                    selectOptions: {
                        collection: function () {
                            return ecommerce.coupons.categories;
                        },
                        labelPath: 'name',
                        valuePath: 'id'
                    },
                    setOptions: {
                        validate: true
                    }
                },
                'input[name=title]': {
                    observe: 'title'
                },
                'select[name=code_type]': {
                    observe: 'coupon_type',
                    selectOptions: {
                        collection: function () {
                            return this.codeTypes;
                        }
                    },
                    onGet: function (val) {
                        if (val === 'Enrollment code') {
                            return 'enrollment';
                        } else if (val === 'Discount code') {
                            return 'discount';
                        }
                        return '';
                    }
                },
                'select[name=voucher_type]': {
                    observe: 'voucher_type',
                    selectOptions: {
                        collection: function () {
                            return this.voucherTypes;
                        }
                    }
                },
                'input[name=benefit_type]': {
                    observe: 'benefit_type'
                },
                '.benefit-addon': {
                    observe: 'benefit_type',
                    onGet: function (val) {
                        if (val === 'Percentage') {
                            return '%';
                        } else if (val === 'Fixed') {
                            return '$';
                        }
                        return '';
                    }
                },
                'input[name=benefit_value]': {
                    observe: 'benefit_value'
                },
                'input[name=client]': {
                    observe: 'client'
                },
                'input[name=course_id]': {
                    observe: 'course_id'
                },
                'input[name=quantity]': {
                    observe: 'quantity'
                },
                'input[name=price]': {
                    observe: 'price'
                },
                'input[name=start_date]': {
                    observe: 'start_date',
                    onGet: function (val) {
                        return Utils.stripTimezone(val);
                    }
                },
                'input[name=end_date]': {
                    observe: 'end_date',
                    onGet: function (val) {
                        return Utils.stripTimezone(val);
                    }
                },
                'input[name=code]': {
                    observe: 'code'
                },
                'input[name=note]': {
                    observe: 'note'
                }
            },

            events: {
                'input [name=course_id]': 'fillFromCourse',

                // catch value after autocomplete
                'blur [name=course_id]': 'fillFromCourse',
                'change [name=seat_type]': 'changeSeatType',
                'change [name=benefit_type]': 'changeUpperLimitForBenefitValue'
            },

            initialize: function (options) {
                this.alertViews = [];
                this.editing = options.editing || false;

                this.listenTo(this.model, 'change:coupon_type', this.toggleFields);
                this.listenTo(this.model, 'change:voucher_type', this.toggleFields);

                this._super();
            },

            changeUpperLimitForBenefitValue: function () {
                var is_benefit_percentage = this.$el.find('[name=code_type]').val() === 'Percentage',
                    max_value = is_benefit_percentage ? '100' : '';

                this.$el.find('[name=benefit_value]').attr('max', max_value);
            },

            toggleFields: function () {
                var couponType = this.model.get('coupon_type'),
                    voucherType = this.model.get('voucher_type'),
                    formGroup = function (sel) {
                        return this.$el.find(sel).closest('.form-group');
                    }.bind(this);

                if (couponType === 'discount') {
                    formGroup('[name=benefit_value]').removeClass('hidden');
                } else {
                    // enrollment
                    formGroup('[name=benefit_value]').addClass('hidden');
                }

                // When creating a discount show the CODE field for both (they are both multi-use)
                //     - Multiple times by multiple customers
                //     - Once per customer
                if (couponType === 'discount' && voucherType !== 'Single use') {
                    formGroup('[name=code]').removeClass('hidden');
                } else {
                    formGroup('[name=code]').addClass('hidden');
                }

                // The only time we allow for a generation of multiple codes is
                // when they are of type single use.
                if (voucherType === 'Single use') {
                    formGroup('[name=quantity]').removeClass('hidden');
                } else {
                    formGroup('[name=quantity]').addClass('hidden');
                }
            },

            /**
             * Fill seat type options from course ID.
             */
            fillFromCourse: _.debounce(function () {
                var courseId = this.$el.find('[name=course_id]').val(),
                    course = Course.findOrCreate({id: courseId}),
                    parseId = _.compose(parseInt, _.property('id'));

                // stickit will not pick it up if this is a blur event
                this.model.set('course_id', courseId);

                course.listenTo(course, 'sync', _.bind(function () {
                    this.seatTypes = _.map(course.seats(), function (seat) {
                        var name = seat.getSeatTypeDisplayName();
                        return $('<option></option>')
                            .text(name)
                            .val(name)
                            .data({
                                price: seat.get('price'),
                                stockrecords: _.map(seat.get('stockrecords'), parseId)
                            });
                    });
                    // update field
                    this.$el.find('[name=seat_type]')
                        .html(this.seatTypes)
                        .trigger('change');

                    if (this.editing) {
                        this.$el.find('[name=seat_type]')
                            .val(_s.capitalize(this.model.get('seat_type')));
                    }
                }, this));

                course.fetch({data: {include_products: true}});
            }, 100),

            /*
             * Update price field and model.stockrecords
             */
            changeSeatType: function () {
                var data, quantity, price,
                    seatType = this.$el.find('[name=seat_type]').val();

                if (!this.editing) {
                    this.model.set('seat_type', seatType);

                    if (seatType && !this.editing) {
                        data = this.$el.find('[value=' + seatType + ']').data();
                        quantity = this.model.get('quantity');
                        price = data.price * quantity;
                        this.model.set('stock_record_ids', data.stockrecords);
                        this.model.set('price', price);
                        this.$el.find('[name=price]').val(price);
                    }
                }
            },

            disableNonEditableFields: function () {
                this.$el.find('input[name=title]').attr('disabled', true);
                this.$el.find('select[name=code_type]').attr('disabled', true);
                this.$el.find('select[name=voucher_type]').attr('disabled', true);
                this.$el.find('input[name=quantity]').attr('disabled', true);
                this.$el.find('input[name=client]').attr('disabled', true);
                this.$el.find('input[name=price]').attr('disabled', true);
                this.$el.find('input[name=course_id]').attr('disabled', true);
                this.$el.find('input[name=code]').attr('disabled', true);
                this.$el.find('input[name=benefit_value]').attr('disabled', true);
                this.$el.find('input[name=benefit_type]').attr('disabled', true);
                this.$el.find('select[name=seat_type]').attr('disabled', true);
                this.$el.find('select[name=category]').attr('disabled', true);
                this.$el.find('input[name=note]').attr('disabled', true);
            },

            render: function () {
                // Render the parent form/template
                this.$el.html(this.template(this.model.attributes));
                this.stickit();

                // Avoid the need to create this jQuery object every time an alert has to be rendered.
                this.$alerts = this.$el.find('.alerts');

                if (this.editing) {
                    this.$el.find('select[name=category]').val(this.model.get('categories')[0].id).trigger('change');
                    this.disableNonEditableFields();
                    this.$el.find('button[type=submit]').html(gettext('Save Changes'));
                    this.fillFromCourse();
                } else {
                    var firstEntry = function(obj, i){ return i === 0 ? obj : null; },
                        defaultCategory = ecommerce.coupons.categories.filter(firstEntry);
                    this.model.set('coupon_type', this.codeTypes[0].value);
                    this.model.set('voucher_type', this.voucherTypes[0].value);
                    this.model.set('category', defaultCategory[0].id);
                    this.model.set('benefit_type', 'Percentage');
                    this.$el.find('[name=benefit_value]').attr('max', 100);
                    this.$el.find('button[type=submit]').html(gettext('Create Coupon'));
                }

                this._super();
                return this;
            },

            /**
             * Override default saveSuccess.
             */
            saveSuccess: function (model, response) {
                this.goTo(response.coupon_id ? response.coupon_id.toString() : response.id.toString());
            }
        });
    }
);
