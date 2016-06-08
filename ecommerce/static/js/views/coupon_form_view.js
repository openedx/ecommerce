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
                    observe: 'invoice_discount_value'
                },
                'input[name=invoice_number]': {
                    observe: 'invoice_number'
                },
                'input[name=invoiced_amount]': {
                    observe: 'invoiced_amount'
                },
                'input[name=invoice_payment_date]': {
                    observe: 'invoice_payment_date',
                    onGet: function (val) {
                        return Utils.stripTimezone(val);
                    }
                },
                'input[name=tax_deducted_source_value]': {
                    observe: 'tax_deducted_source_value'
                },
                'input[name=tax_deducted_source]': {
                    observe: 'tax_deducted_source'
                }
            },

            events: {
                'input [name=course_id]': 'fillFromCourse',
                'input [name=quantity]': 'changeTotalValue',

                // catch value after autocomplete
                'blur [name=course_id]': 'fillFromCourse',
                'change [name=seat_type]': 'changeSeatType',
                'change [name=benefit_type]': 'changeUpperLimitForBenefitValue',
                'change [name=invoice_discount_type]': 'changeUpperLimitForInvoiceDiscountValue',
                'change [name=invoice_type]': 'toggleInvoiceFields',
                'change [name=tax_deducted_source]': 'toggleTaxDeductedSourceField'
            },

            initialize: function (options) {
                this.alertViews = [];
                this.editing = options.editing || false;
                this.hiddenClass = 'hidden';

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

            changeUpperLimitForBenefitValue: function () {
                var is_benefit_percentage = this.$el.find('[name=benefit_type]:checked').val() === 'Percentage',
                    max_value = is_benefit_percentage ? '100' : '';

                this.$el.find('[name=benefit_value]').attr('max', max_value);
            },

            changeUpperLimitForInvoiceDiscountValue: function () {
                var is_invoice_discount_percentage = this.$el.find(
                    '[name=invoice_discount_type]:checked').val() === 'Percentage',
                    max_value = is_invoice_discount_percentage ? '100' : '';

                this.$el.find('[name=invoice_discount_value]').attr('max', max_value);
            },

            formGroup: function (el) {
                return this.$el.find(el).closest('.form-group');
            },

            emptyCodeField: function () {
                this.model.set('code', '');
            },

            toggleDollarPercentIcon: function (val) {
                if (val === 'Percentage') {
                    return '%';
                } else if (val === 'Absolute') {
                    return '$';
                } else {
                    return '';
                }
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
                    this.formGroup('[name=benefit_value]').removeClass(this.hiddenClass);
                    if (parseInt(this.model.get('quantity')) === 1) {
                        this.formGroup('[name=code]').removeClass(this.hiddenClass);
                    }
                    if (this.model.get('voucher_type') !== 'Single use') {
                        this.formGroup('[name=code]').removeClass(this.hiddenClass);
                    }
                } else {
                    this.formGroup('[name=benefit_value]').addClass(this.hiddenClass);
                    this.formGroup('[name=code]').addClass(this.hiddenClass);
                }
            },

            toggleCatalogTypeField: function () {
                if (this.model.get('catalog_type') === 'Single course') {
                    this.formGroup('[name=catalog_query]').addClass(this.hiddenClass);
                    this.formGroup('[name=course_seat_types]').addClass(this.hiddenClass);
                    this.formGroup('[name=course_id]').removeClass(this.hiddenClass);
                    this.formGroup('[name=seat_type]').removeClass(this.hiddenClass);
                } else {
                    this.formGroup('[name=catalog_query]').removeClass(this.hiddenClass);
                    this.formGroup('[name=course_seat_types]').removeClass(this.hiddenClass);
                    this.formGroup('[name=course_id]').addClass(this.hiddenClass);
                    this.formGroup('[name=seat_type]').addClass(this.hiddenClass);
                }
            },

            toggleVoucherTypeField: function () {
                var voucherType = this.model.get('voucher_type');
                if (!this.editing) {
                    this.emptyCodeField();
                }
                // When creating a Once by multiple customers code show the usage number field.
                if (voucherType !== 'Single use') {
                    if (this.model.get('coupon_type') === 'Discount code') {
                        this.formGroup('[name=code]').removeClass(this.hiddenClass);
                    }
                    this.formGroup('[name=max_uses]').removeClass(this.hiddenClass);
                } else {
                    this.formGroup('[name=max_uses]').addClass(this.hiddenClass);
                }

                // The only time we allow for a generation of multiple codes is
                // when they are of type single use.
                if (voucherType === 'Single use') {
                    this.formGroup('[name=quantity]').removeClass(this.hiddenClass);
                } else {
                    this.formGroup('[name=quantity]').addClass(this.hiddenClass);
                }
            },

            toggleInvoiceFields: function () {
                var invoice_type = this.$el.find('[name=invoice_type]:checked').val();
                var prepaid_fields = [
                    this.formGroup('[name=invoice_number]'),
                    this.formGroup('[name=invoiced_amount]'),
                    this.formGroup('[name=invoice_payment_date]')
                ];
                var self = this;
                if (invoice_type === 'Postpaid') {
                    _.each(prepaid_fields, function(field) {
                        field.addClass(self.hiddenClass);
                    });
                    self.formGroup('[name=invoice_discount_value]').removeClass(this.hiddenClass);
                } else if (invoice_type === 'Prepaid') {
                    _.each(prepaid_fields, function(field) {
                        field.removeClass(self.hiddenClass);
                    });
                    self.formGroup('[name=invoice_discount_value]').addClass(this.hiddenClass);
                }
            },

            toggleTaxDeductedSourceField: function() {
                var tax_deducted_source = this.$el.find('[name=tax_deducted_source]:checked').val();
                if (tax_deducted_source === 'Yes') {
                    this.formGroup('[name=tax_deducted_source_value]').removeClass(this.hiddenClass);
                } else if (tax_deducted_source === 'No') {
                    this.formGroup('[name=tax_deducted_source_value]').addClass(this.hiddenClass);
                }
            },

            /**
             * When Discount code selected, code entered and Single use selected hide quantity field
             * Show field when code empty and Single use selected
             */
            toggleCodeField: function () {
                var voucherType = this.model.get('voucher_type');
                if (this.model.get('coupon_type') === 'Discount code') {
                    if (this.model.get('code') !== '' && voucherType === 'Single use') {
                        this.formGroup('[name=quantity]').addClass(this.hiddenClass);
                    } else if (voucherType === 'Single use') {
                        this.formGroup('[name=quantity]').removeClass(this.hiddenClass);
                    }
                }
            },

            /**
             * When Discount code selected, Single use selected and
             * quantity greater than 1 hide code field
             */
            toggleQuantityField: function () {
                var voucherType = this.model.get('voucher_type');
                if (this.model.get('coupon_type') === 'Discount code') {
                    if (parseInt(this.model.get('quantity')) !== 1 && voucherType === 'Single use') {
                        this.formGroup('[name=code]').addClass(this.hiddenClass);
                    } else if (voucherType === 'Single use') {
                        this.formGroup('[name=code]').removeClass(this.hiddenClass);
                    }
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
                var quantity = this.$el.find('input[name=quantity]').val(),
                    totalValue = quantity * seatData.price;
                this.model.set('total_value', totalValue);
                this.$el.find('input[name=price]').val(totalValue);
            },

            disableNonEditableFields: function () {
                this.$el.find('select[name=code_type]').attr('disabled', true);
                this.$el.find('select[name=voucher_type]').attr('disabled', true);
                this.$el.find('input[name=quantity]').attr('disabled', true);
                this.$el.find('input[name=course_id]').attr('disabled', true);
                this.$el.find('input[name=code]').attr('disabled', true);
                this.$el.find('input[name=benefit_type]').attr('disabled', true);
                this.$el.find('select[name=seat_type]').attr('disabled', true);
                this.$el.find('input[name=max_uses]').attr('disabled', true);
                this.$el.find('input[name=catalog_type]').attr('disabled', true);
            },

            getSeatData: function () {
                return this.$el.find('[value=' + this.getSeatType() + ']').data();
            },

            getSeatType: function () {
                return this.$el.find('[name=seat_type]').val();
            },

            updateCatalogQuery: function() {
                this.dynamic_catalog_view.query = this.model.get('catalog_query');
            },

            updateCourseSeatTypes: function() {
                this.dynamic_catalog_view.seat_types = this.model.get('course_seat_types');
            },

            render: function () {
                // Render the parent form/template
                this.$el.html(this.template(this.model.attributes));
                this.stickit();

                this.toggleCatalogTypeField();
                this.dynamic_catalog_view.setElement(this.$el.find('.catalog_buttons')).render();

                // Avoid the need to create this jQuery object every time an alert has to be rendered.
                this.$alerts = this.$el.find('.alerts');

                if (this.editing) {
                    this.$el.find('select[name=category]').val(this.model.get('categories')[0].id).trigger('change');
                    this.disableNonEditableFields();
                    this.toggleCouponTypeField();
                    this.toggleVoucherTypeField();
                    this.toggleCodeField();
                    this.toggleQuantityField();
                    this.$el.find('.catalog-query').addClass('editing');
                    this.$el.find('button[type=submit]').html(gettext('Save Changes'));
                    this.$el.find('[name=invoice_type]').trigger('change');
                    this.$el.find('[name=tax_deducted_source]').trigger('change');
                    this.fillFromCourse();
                } else {
                    var firstEntry = function(obj, i){ return i === 0 ? obj : null; },
                        defaultCategory = ecommerce.coupons.categories.filter(firstEntry);
                    this.model.set('coupon_type', this.codeTypes[0].value);
                    this.model.set('voucher_type', this.voucherTypes[0].value);
                    this.model.set('category', defaultCategory[0].id);
                    this.model.set('benefit_type', 'Percentage');
                    this.model.set('catalog_type', 'Single course');
                    this.model.set('invoice_discount_type', 'Percentage');
                    this.model.set('invoice_type', 'Prepaid');
                    this.model.set('tax_deducted_source', 'No');
                    this.$el.find('[name=benefit_value]').attr('max', 100);
                    this.$el.find('[name=invoice_discount_value]').attr('max', 100);
                    this.$el.find('button[type=submit]').html(gettext('Create Coupon'));
                    this.$el.find('.catalog-query').removeClass('editing');
                }

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
