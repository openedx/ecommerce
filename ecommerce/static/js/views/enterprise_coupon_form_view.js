/* eslint no-underscore-dangle: ["error", { "allow": ["_initAttributes", "_super"] }] */

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
    'text!templates/_alert_div.html',
    'text!templates/enterprise_coupon_form.html',
    'views/form_view'
],
    function($,
              Backbone,
              BackboneSuper,
              BackboneValidation,
              BackboneStickit,
              ecommerce,
              _,
              _s,
              Utils,
              AlertDivTemplate,
              CouponFormTemplate,
              FormView) {
        'use strict';

        return FormView.extend({
            tagName: 'form',

            className: 'coupon-form-view',

            template: _.template(CouponFormTemplate),

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
                    label: gettext('Can be used multiple times by multiple customers')
                }
            ],

            bindings: {
                'select[name=category]': {
                    observe: 'category',
                    selectOptions: {
                        collection: function() {
                            return ecommerce.coupons.categories;
                        },
                        labelPath: 'name',
                        valuePath: 'id'
                    },
                    setOptions: {
                        validate: true
                    },
                    onGet: function(val) {
                        return val.id;
                    },
                    onSet: function(val) {
                        return {
                            id: val,
                            name: $('select[name=category] option:selected').text()
                        };
                    }
                },
                'input[name=title]': {
                    observe: 'title'
                },
                'select[name=code_type]': {
                    observe: 'coupon_type',
                    selectOptions: {
                        collection: function() {
                            return this.codeTypes;
                        }
                    }
                },
                'select[name=voucher_type]': {
                    observe: 'voucher_type',
                    selectOptions: {
                        collection: function() {
                            return this.voucherTypes;
                        }
                    }
                },
                'input[name=benefit_type]': {
                    observe: 'benefit_type'
                },
                '.benefit-addon': {
                    observe: 'benefit_type',
                    onGet: function(val) {
                        return this.toggleDollarPercentIcon(val);
                    }
                },
                'input[name=benefit_value]': {
                    observe: 'benefit_value'
                },
                'input[name=quantity]': {
                    observe: 'quantity'
                },
                'input[name=price]': {
                    observe: 'price'
                },
                'input[name=start_date]': {
                    observe: 'start_date',
                    onGet: function(val) {
                        return Utils.stripTimezone(val);
                    }
                },
                'input[name=end_date]': {
                    observe: 'end_date',
                    onGet: function(val) {
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
                'input[name=email_domains]': {
                    observe: 'email_domains',
                    onSet: function(val) {
                        return val.replace(/\s/g, '').toLowerCase();
                    }
                },
                'input[name=invoice_type]': {
                    observe: 'invoice_type'
                },
                'input[name=invoice_discount_type]': {
                    observe: 'invoice_discount_type'
                },
                '.invoice-discount-addon': {
                    observe: 'invoice_discount_type',
                    onGet: function(val) {
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
                    onGet: function(val) {
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
                },
                'select[name=enterprise_customer]': {
                    observe: 'enterprise_customer',
                    selectOptions: {
                        collection: function() {
                            return ecommerce.coupons.enterprise_customers;
                        },
                        defaultOption: {id: '', name: ''},
                        labelPath: 'name',
                        valuePath: 'id'
                    },
                    setOptions: {
                        validate: true
                    },
                    onGet: function(val) {
                        return _.isUndefined(val) || _.isNull(val) ? '' : val.id;
                    },
                    onSet: function(val) {
                        return {
                            id: val,
                            name: $('select[name=enterprise_customer] option:selected').text()
                        };
                    }
                },
                'input[name=enterprise_customer_catalog]': {
                    observe: 'enterprise_customer_catalog'
                }
            },

            events: {
                // catch value after autocomplete
                'change [name=benefit_type]': 'changeLimitForBenefitValue',
                'change [name=invoice_discount_type]': 'changeLimitForInvoiceDiscountValue',
                'change [name=invoice_type]': 'toggleInvoiceFields',
                'change [name=tax_deduction]': 'toggleTaxDeductedSourceField',
                'click .external-link': 'routeToLink',
                'click #cancel-button': 'cancelButtonClicked'
            },

            initialize: function(options) {
                this.alertViews = [];
                this.editing = options.editing || false;
                this.hiddenClass = 'hidden';
                if (this.editing) {
                    this.editableAttributes = [
                        'benefit_value',
                        'category',
                        'end_date',
                        'enterprise_customer',
                        'enterprise_customer_catalog',
                        'invoice_discount_type',
                        'invoice_discount_value',
                        'invoice_number',
                        'invoice_payment_date',
                        'invoice_type',
                        'max_uses',
                        'note',
                        'price',
                        'start_date',
                        'tax_deducted_source',
                        'title',
                        'email_domains'
                    ];

                    // Store initial model attribute values in order to revert to them when cancel button is clicked.
                    this._initAttributes = $.extend(true, {}, this.model.attributes);
                }

                this.listenTo(this.model, 'change:coupon_type', this.toggleCouponTypeField);
                this.listenTo(this.model, 'change:voucher_type', this.toggleVoucherTypeField);
                this.listenTo(this.model, 'change:code', this.toggleCodeField);
                this.listenTo(this.model, 'change:quantity', this.toggleQuantityField);

                this._super();
            },

            cancelButtonClicked: function() {
                this.model.set(this._initAttributes);
            },

            setLimitToElement: function(element, maxValue, minValue) {
                element.attr({max: maxValue, min: minValue});
            },

            changeLimitForBenefitValue: function() {
                var isBenefitPercentage = this.$('[name=benefit_type]:checked').val() === 'Percentage',
                    maxValue = isBenefitPercentage ? '100' : '';

                this.setLimitToElement(this.$('[name=benefit_value]'), maxValue, 1);
            },

            changeLimitForInvoiceDiscountValue: function() {
                var isInvoiceDiscountPercentage = this.$(
                    '[name=invoice_discount_type]:checked').val() === 'Percentage',
                    maxValue = isInvoiceDiscountPercentage ? '100' : '';

                this.setLimitToElement(this.$('[name=invoice_discount_value]'), maxValue, 1);
            },

            toggleDollarPercentIcon: function(val) {
                var icon = '';
                if (val === 'Percentage') {
                    icon = '%';
                } else if (val === 'Absolute') {
                    icon = '$';
                }
                return icon;
            },

            formGroup: function(el) {
                return this.$(el).closest('.form-group');
            },

            emptyCodeField: function() {
                this.model.set('code', '');
            },

            /**
             * When creating a discount show the DISCOUNT VALUE and CODE field for both
             * - Can be used once by one customer
             * - Can be used once by multiple customers
             */
            toggleCouponTypeField: function() {
                if (!this.editing) {
                    this.emptyCodeField();
                }
                if (this.model.get('coupon_type') === 'Discount code') {
                    this.changeLimitForBenefitValue();
                    this.formGroup('[name=benefit_value]').removeClass(this.hiddenClass);
                    if (parseInt(this.model.get('quantity'), 10) === 1) {
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

            toggleInvoiceFields: function() {
                var invoiceType = this.$('[name=invoice_type]:checked').val(),
                    prepaidFields = [
                        '[name=invoice_number]',
                        '[name=invoice_payment_date]'
                    ];

                if (invoiceType === 'Postpaid') {
                    _.each(prepaidFields, function(field) {
                        this.hideField(field, null);
                    }, this);
                    this.hideField('[name=price]', 0);
                    this.formGroup('[name=invoice_discount_value]').removeClass(this.hiddenClass);
                    this.formGroup('[name=tax_deduction]').removeClass(this.hiddenClass);
                } else if (invoiceType === 'Prepaid') {
                    _.each(prepaidFields, function(field) {
                        this.formGroup(field).removeClass(this.hiddenClass);
                    }, this);
                    this.formGroup('[name=price]').removeClass(this.hiddenClass);
                    this.hideField('[name=invoice_discount_value]', null);
                    this.formGroup('[name=tax_deduction]').removeClass(this.hiddenClass);
                } else if (invoiceType === 'Not-Applicable') {
                    _.each(prepaidFields, function(field) {
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
                var taxDeduction = this.$('[name=tax_deduction]:checked').val();
                if (taxDeduction === 'Yes') {
                    this.formGroup('[name=tax_deducted_source_value]').removeClass(this.hiddenClass);
                } else if (taxDeduction === 'No') {
                    this.hideField('[name=tax_deducted_source_value]', null);
                }
            },

            // Hiding a field should change the field's value to a default one.
            hideField: function(fieldName, value) {
                var field = this.$(fieldName);
                this.formGroup(fieldName).addClass(this.hiddenClass);
                field.val(value);
                field.trigger('change');
            },

            toggleVoucherTypeField: function() {
                var maxUsesFieldSelector = '[name=max_uses]',
                    maxUsesModelValue = this.model.get('max_uses'),
                    multiUseMaxUsesValue = this.editing ? maxUsesModelValue : null,
                    voucherType = this.model.get('voucher_type');
                if (!this.editing) {
                    this.emptyCodeField();
                }
                /* When creating a ONCE_PER_CUSTOMER or MULTI_USE code show the usage number field.
                *  Show the code field only for discount coupons and when the quantity is 1 to avoid
                *  integrity issues.
                */
                if (voucherType === 'Single use') {
                    this.setLimitToElement(this.$(maxUsesFieldSelector), '', '');
                    this.hideField(maxUsesFieldSelector, '');
                    this.model.unset('max_uses');
                } else {
                    if (this.model.get('coupon_type') === 'Discount code' && this.$('[name=quantity]').val() === 1) {
                        this.formGroup('[name=code]').removeClass(this.hiddenClass);
                    }
                    this.formGroup(maxUsesFieldSelector).removeClass(this.hiddenClass);
                    /* For coupons that can be used multiple times by multiple users, the max_uses
                     * field needs to be empty by default and the minimum can not be less than 2.
                     */
                    if (voucherType === 'Multi-use') {
                        this.model.set('max_uses', multiUseMaxUsesValue);
                        if (this.editing) {
                            this.setLimitToElement(this.$(maxUsesFieldSelector), '', multiUseMaxUsesValue);
                        } else {
                            this.setLimitToElement(this.$(maxUsesFieldSelector), '', 2);
                        }
                    } else if (this.editing) {
                        this.setLimitToElement(this.$(maxUsesFieldSelector), '', maxUsesModelValue);
                    } else {
                        this.model.set('max_uses', 1);
                        this.setLimitToElement(this.$(maxUsesFieldSelector), '', 1);
                    }
                }
            },

            /**
             * When Discount code selected and code entered hide quantity field.
             * Show field when code empty.
             */
            toggleCodeField: function() {
                if (this.model.get('coupon_type') === 'Discount code') {
                    if (this.model.get('code')) {
                        this.hideField('[name=quantity]', 1);
                    } else {
                        this.formGroup('[name=quantity]').removeClass(this.hiddenClass);
                    }
                }
            },

            /**
             * When Discount code selected and quantity greater than 1 hide code field.
             */
            toggleQuantityField: function() {
                if (this.model.get('coupon_type') === 'Discount code') {
                    if (parseInt(this.model.get('quantity'), 10) !== 1) {
                        this.hideField('[name=code]', '');
                    } else {
                        this.formGroup('[name=code]').removeClass(this.hiddenClass);
                    }
                }
            },

            disableNonEditableFields: function() {
                this.$('.non-editable').attr('disabled', true);
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

            render: function() {
                // Render the parent form/template
                var customerId = '';

                this.$el.html(this.template(this.model.attributes));
                this.stickit();

                this.$('.row:first').before(AlertDivTemplate);

                if (this.editing) {
                    if (_.isString(this.model.get('enterprise_customer'))) {
                        // API returns a string value for enterprise customer
                        customerId = this.model.get('enterprise_customer');
                        this.model.set('enterprise_customer', {id: customerId});
                    }

                    this.disableNonEditableFields();
                    this.toggleCouponTypeField();
                    this.toggleVoucherTypeField();
                    this.toggleCodeField();
                    this.toggleQuantityField();
                    this.$('button[type=submit]').html(gettext('Save Changes'));
                    this.$('[name=invoice_type]').trigger('change');
                    this.$('[name=tax_deduction]').trigger('change');
                } else {
                    this.model.set({
                        coupon_type: this.codeTypes[0].value,
                        voucher_type: this.voucherTypes[0].value,
                        benefit_type: 'Percentage',
                        invoice_discount_type: 'Percentage',
                        invoice_type: 'Prepaid',
                        tax_deduction: 'No'
                    });
                    this.$('button[type=submit]').html(gettext('Create Coupon'));
                }

                if (this.$('[name=invoice_discount_type]:checked').val() === 'Percentage') {
                    this.setLimitToElement(this.$('[name=invoice_discount_value]'), 100, 1);
                }
                if (this.$('[name=benefit_type]:checked').val() === 'Percentage') {
                    this.setLimitToElement(this.$('[name=benefit_value]'), 100, 1);
                }

                // Add date picker
                Utils.addDatePicker(this);

                this._super();
                return this;
            },

            /**
             * Override default saveSuccess.
             */
            saveSuccess: function(model, response) {
                this.goTo(response.coupon_id ? response.coupon_id.toString() : response.id.toString());
            }
        });
    }
);
