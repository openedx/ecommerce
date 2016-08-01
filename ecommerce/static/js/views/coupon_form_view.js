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
        'collections/course_collection',
        'views/form_view',
        'views/dynamic_catalog_view',
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
              Courses,
              FormView,
              DynamicCatalogView) {
        'use strict';

        return FormView.extend({
            tagName: 'form',

            className: 'coupon-form-view',

            template: _.template(CouponFormTemplate),

            seatTypes: [],

            codeTypes: [
                {
                    value: 'Enrollment code',
                    label: gettext('Enrollment Code')
                },
                {
                    value: 'Discount code',
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
                },
                {
                    value: 'Multi-use',
                    label: gettext('Can be used multiple times by multiple customers'),
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
                        valuePath: 'name'
                    },
                    setOptions: {
                        validate: true
                    },
                    onGet: function (val) {
                        return val;
                    },
                    onSet: function (val) {
                        return val;
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
                        return this.toggleDollarPercentIcon(val);
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
                'input[name=total_value]': {
                    observe: 'total_value'
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
                },
                'input[name=max_uses]': {
                    observe: 'max_uses'
                },
                'input[name=catalog_type]': {
                    observe: 'catalog_type'
                },
                'textarea[name=catalog_query]': {
                    observe: 'catalog_query'
                },
                'input[name=course_seat_types]': {
                    observe: 'course_seat_types'
                },
                'input[name=invoice_type]': {
                    observe: 'invoice_type'
                },
                'input[name=invoice_discount_type]': {
                    observe: 'invoice_discount_type'
                },
                '.invoice-discount-addon': {
                    observe: 'invoice_discount_type',
                    onGet: function (val) {
                        return this.toggleDollarPercentIcon(val);
                    }
                },
                'input[name=invoice_discount_value]': {
                    observe: 'invoice_discount_value',
                    onSet: function(val) {
                        if (val === '') {
                            return null;
                        }
                        return val;
                    }
                },
                'input[name=invoice_number]': {
                    observe: 'invoice_number'
                },
                'input[name=invoice_payment_date]': {
                    observe: 'invoice_payment_date',
                    onGet: function (val) {
                        return Utils.stripTimezone(val);
                    },
                    onSet: function(val) {
                        if (val === '') {
                            return null;
                        }
                        return val;
                    }
                },
                'input[name=tax_deduction]': {
                    observe: 'tax_deduction'
                },
                'input[name=tax_deducted_source_value]': {
                    observe: 'tax_deducted_source',
                    onSet: function(val) {
                        if (val === '') {
                            return null;
                        }
                        return val;
                    }
                }
            },

            events: {
                'input [name=course_id]': 'fillFromCourse',
                'input [name=quantity]': 'changeTotalValue',

                // catch value after autocomplete
                'blur [name=course_id]': 'fillFromCourse',
                'change [name=seat_type]': 'changeSeatType',
                'change [name=benefit_type]': 'changeLimitForBenefitValue',
                'change [name=invoice_discount_type]': 'changeLimitForInvoiceDiscountValue',
                'change [name=invoice_type]': 'toggleInvoiceFields',
                'change [name=tax_deduction]': 'toggleTaxDeductedSourceField',
                'click .external-link': 'routeToLink'
            },

            initialize: function (options) {
                this.alertViews = [];
                this.editing = options.editing || false;
                this.hiddenClass = 'hidden';

                if (this.editing) {
                    this.editableAttributes = [
                        'benefit_value',
                        'catalog_query',
                        'category',
                        'client',
                        'course_seat_types',
                        'end_date',
                        'invoice_discount_type',
                        'invoice_discount_value',
                        'invoice_number',
                        'invoice_payment_date',
                        'invoice_type',
                        'note',
                        'price',
                        'start_date',
                        'tax_deducted_source',
                        'title',
                    ];
                }

                this.dynamic_catalog_view = new DynamicCatalogView({
                    'query': this.model.get('catalog_query'),
                    'seat_types': this.model.get('course_seat_types')
                });

                this.listenTo(this.model, 'change:coupon_type', this.toggleCouponTypeField);
                this.listenTo(this.model, 'change:voucher_type', this.toggleVoucherTypeField);
                this.listenTo(this.model, 'change:code', this.toggleCodeField);
                this.listenTo(this.model, 'change:quantity', this.toggleQuantityField);
                this.listenTo(this.model, 'change:catalog_type', this.toggleCatalogTypeField);
                this.listenTo(this.model, 'change:catalog_query', this.updateCatalogQuery);
                this.listenTo(this.model, 'change:course_seat_types', this.updateCourseSeatTypes);

                this._super();
            },

            setLimitToElement: function(element, max_value, min_value) {
                element.attr({ 'max': max_value, 'min': min_value });
            },

            changeLimitForBenefitValue: function () {
                var is_benefit_percentage = this.$('[name=benefit_type]:checked').val() === 'Percentage',
                    max_value = is_benefit_percentage ? '100' : '';

                this.setLimitToElement(this.$('[name=benefit_value]'), max_value, 1);
            },

            changeLimitForInvoiceDiscountValue: function () {
                var is_invoice_discount_percentage = this.$(
                    '[name=invoice_discount_type]:checked').val() === 'Percentage',
                    max_value = is_invoice_discount_percentage ? '100' : '';

                this.setLimitToElement(this.$('[name=invoice_discount_value]'), max_value, 1);
            },

            toggleDollarPercentIcon: function (val) {
                var icon = '';
                if (val === 'Percentage') {
                    icon = '%';
                } else if (val === 'Absolute') {
                    icon = '$';
                }
                return icon;
            },

            formGroup: function (el) {
                return this.$(el).closest('.form-group');
            },

            emptyCodeField: function () {
                this.model.set('code', '');
            },

            /**
             * When creating a discount show the DISCOUNT VALUE and CODE field for both
             * - Can be used once by one customer
             * - Can be used once by multiple customers
             */
            toggleCouponTypeField: function () {
                if (!this.editing) {
                    this.emptyCodeField();
                }
                if (this.model.get('coupon_type') === 'Discount code') {
                    this.changeLimitForBenefitValue();
                    this.formGroup('[name=benefit_value]').removeClass(this.hiddenClass);
                    if (parseInt(this.model.get('quantity')) === 1) {
                        this.formGroup('[name=code]').removeClass(this.hiddenClass);
                    }
                    if (this.model.get('voucher_type') !== 'Single use') {
                        this.formGroup('[name=code]').removeClass(this.hiddenClass);
                    }
                } else {
                    this.setLimitToElement(this.$('[name=benefit_value]'), '', '');
                    this.formGroup('[name=benefit_value]').addClass(this.hiddenClass);
                    this.formGroup('[name=code]').addClass(this.hiddenClass);
                }
            },

            toggleInvoiceFields: function () {
                var invoice_type = this.$('[name=invoice_type]:checked').val(),
                    prepaid_fields = [
                        '[name=invoice_number]',
                        '[name=invoice_payment_date]'
                    ];

                if (invoice_type === 'Postpaid') {
                    _.each(prepaid_fields, function(field) {
                        this.hideField(field, null);
                    }, this);
                    this.hideField('[name=price]', 0);
                    this.formGroup('[name=invoice_discount_value]').removeClass(this.hiddenClass);
                    this.formGroup('[name=tax_deduction]').removeClass(this.hiddenClass);
                } else if (invoice_type === 'Prepaid') {
                    _.each(prepaid_fields, function(field) {
                        this.formGroup(field).removeClass(this.hiddenClass);
                    }, this);
                    this.formGroup('[name=price]').removeClass(this.hiddenClass);
                    this.hideField('[name=invoice_discount_value]', null);
                    this.formGroup('[name=tax_deduction]').removeClass(this.hiddenClass);
                } else if (invoice_type === 'Not-Applicable') {
                    _.each(prepaid_fields, function(field) {
                        this.hideField(field, null);
                    }, this);
                    this.hideField('[name=price]', 0);
                    this.hideField('[name=invoice_discount_value]', null);
                    this.hideField('[name=tax_deducted_source_value]', null);
                    this.$('#non-tax-deducted').prop('checked', true).trigger('change');
                    this.hideField('[name=tax_deduction]', null);
                }
            },

            toggleTaxDeductedSourceField: function() {
                var tax_deduction = this.$('[name=tax_deduction]:checked').val();
                if (tax_deduction === 'Yes') {
                    this.formGroup('[name=tax_deducted_source_value]').removeClass(this.hiddenClass);
                } else if (tax_deduction === 'No') {
                    this.hideField('[name=tax_deducted_source_value]', null);
                }
            },

            toggleCatalogTypeField: function() {
                if (this.model.get('catalog_type') === 'Single course') {
                    this.model.set('course_seat_types', []);
                    this.model.unset('catalog_query');
                    this.formGroup('[name=catalog_query]').addClass(this.hiddenClass);
                    this.formGroup('[name=course_seat_types]').addClass(this.hiddenClass);
                    this.formGroup('[name=course_id]').removeClass(this.hiddenClass);
                    this.formGroup('[name=seat_type]').removeClass(this.hiddenClass);
                } else {
                    this.formGroup('[name=catalog_query]').removeClass(this.hiddenClass);
                    this.formGroup('[name=course_seat_types]').removeClass(this.hiddenClass);
                    this.formGroup('[name=course_id]').addClass(this.hiddenClass);
                    this.formGroup('[name=seat_type]').addClass(this.hiddenClass);
                    this.model.unset('course_id');
                    this.model.unset('seat_type');
                }
            },

            // Hiding a field should change the field's value to a default one.
            hideField: function(field_name, value) {
                var field = this.$(field_name);
                this.formGroup(field_name).addClass(this.hiddenClass);
                field.val(value);
                field.trigger('change');
            },

            toggleVoucherTypeField: function () {
                var voucherType = this.model.get('voucher_type');
                if (!this.editing) {
                    this.emptyCodeField();
                }
                /* When creating a ONCE_PER_CUSTOMER or MULTI_USE code show the usage number field.
                *  Show the code field only for discount coupons and when the quantity is 1 to avoid
                *  integrity issues.
                */
                if (voucherType !== 'Single use') {
                    if (this.model.get('coupon_type') === 'Discount code' && this.$('[name=quantity]').val() === 1) {
                        this.formGroup('[name=code]').removeClass(this.hiddenClass);
                    }
                    this.formGroup('[name=max_uses]').removeClass(this.hiddenClass);
                } else {
                    this.hideField('[name=max_uses]', 1);
                }
            },

            /**
             * When Discount code selected and code entered hide quantity field.
             * Show field when code empty.
             */
            toggleCodeField: function () {
                if (this.model.get('coupon_type') === 'Discount code') {
                    if (this.model.get('code') !== '') {
                        this.hideField('[name=quantity]', 1);
                    } else {
                        this.formGroup('[name=quantity]').removeClass(this.hiddenClass);
                    }
                }
            },

            /**
             * When Discount code selected and quantity greater than 1 hide code field.
             */
            toggleQuantityField: function () {
                if (this.model.get('coupon_type') === 'Discount code') {
                    if (parseInt(this.model.get('quantity')) !== 1) {
                        this.hideField('[name=code]', '');
                    } else {
                        this.formGroup('[name=code]').removeClass(this.hiddenClass);
                    }
                }
            },

            /**
             * Fill seat type options from course ID.
             */
            fillFromCourse: function () {
                var courseId = this.$('[name=course_id]').val(),
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
                    this.$('[name=seat_type]')
                        .html(this.seatTypes)
                        .trigger('change');

                    if (this.editing) {
                        this.$('[name=seat_type]')
                            .val(_s.capitalize(this.model.get('seat_type')));
                    }
                }, this));

                course.fetch({data: {include_products: true}});
            },

            /**
             * Update price field and model.stockrecords.
             */
            changeSeatType: function () {
                var seatType = this.getSeatType(),
                    seatData = this.getSeatData();

                if (!this.editing) {
                    this.model.set('seat_type', seatType);

                    if (seatType && !this.editing) {
                        this.model.set('stock_record_ids', seatData.stockrecords);
                        this.updateTotalValue(seatData);
                    }
                }
            },

            changeTotalValue: function () {
                this.updateTotalValue(this.getSeatData());
            },

            updateTotalValue: function (seatData) {
                var quantity = this.$('input[name=quantity]').val(),
                    totalValue = quantity * seatData.price;
                this.model.set('total_value', totalValue);
                this.model.set('price', totalValue);
            },

            disableNonEditableFields: function () {
                this.$('.non-editable').attr('disabled', true);
            },

            getSeatData: function () {
                return this.$('[value=' + this.getSeatType() + ']').data();
            },

            getSeatType: function () {
                return this.$('[name=seat_type]').val();
            },

            updateCatalogQuery: function() {
                this.dynamic_catalog_view.query = this.model.get('catalog_query');
            },

            updateCourseSeatTypes: function() {
                this.dynamic_catalog_view.seat_types = this.model.get('course_seat_types');
            },

            /**
             * Open external links in a new tab.
             * Works only for anchor elements that contain 'external-link' class.
             */
            routeToLink: function(e) {
                e.preventDefault();
                e.stopPropagation();
                window.open(e.currentTarget.href);
            },


            /**
             * Override default renderAlert to display a custom message.
             */
            renderAlert: function (level, title, message) {
                if (!this.model.isValid(true)) {
                    message = 'Please complete all required fields.';
                }
                this._super(level, title='', message);
            },

            render: function () {
                // Render the parent form/template
                this.$el.html(this.template(this.model.attributes));
                this.stickit();

                this.toggleCatalogTypeField();
                this.dynamic_catalog_view.setElement(this.$('.catalog_buttons')).render();

                // Avoid the need to create this jQuery object every time an alert has to be rendered.
                this.$alerts = this.$('.alerts');

                if (this.editing) {
                    this.disableNonEditableFields();
                    this.toggleCouponTypeField();
                    this.toggleVoucherTypeField();
                    this.toggleCodeField();
                    this.toggleQuantityField();
                    this.$('.catalog-query').addClass('editing');
                    this.$('button[type=submit]').html(gettext('Save Changes'));
                    this.$('[name=invoice_type]').trigger('change');
                    this.$('[name=tax_deduction]').trigger('change');
                    this.fillFromCourse();
                } else {
                    this.model.set({
                        'coupon_type': this.codeTypes[0].value,
                        'voucher_type': this.voucherTypes[0].value,
                        'benefit_type': 'Percentage',
                        'catalog_type': 'Single course',
                        'invoice_discount_type': 'Percentage',
                        'invoice_type': 'Prepaid',
                        'tax_deduction': 'No',
                    });
                    this.$('button[type=submit]').html(gettext('Create Coupon'));
                    this.$('.catalog-query').removeClass('editing');
                }

                this.setLimitToElement(this.$('[name=invoice_discount_value]'), 100, 1);
                this.setLimitToElement(this.$('[name=benefit_value]'), 100, 1);

                // Add date picker
                Utils.addDatePicker(this);

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
