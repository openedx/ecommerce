/* eslint no-underscore-dangle: ["error", { "allow": ["_initAttributes", "_super"] }] */

define([
    'jquery',
    'backbone',
    'backbone.super',
    'backbone.validation',
    'ecommerce',
    'underscore',
    'text!templates/enterprise_coupon_form.html',
    'views/coupon_form_view'
],
    function($,
              Backbone,
              BackboneSuper,
              BackboneValidation,
              ecommerce,
              _,
              EnterpriseCouponFormTemplate,
              CouponFormView) {
        'use strict';

        return CouponFormView.extend({
            template: _.template(EnterpriseCouponFormTemplate),

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
                },
                {
                    value: 'Multi-use-per-Customer',
                    label: gettext('Can be used multiple times by one customer')
                }
            ],

            couponBindings: {
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
                },
                'input[name=notify_email]': {
                    observe: 'notify_email',
                    onSet: function(val) {
                        return val === '' ? null : val;
                    }
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

            getEditableAttributes: function() {
                return [
                    'benefit_value',
                    'category',
                    'end_date',
                    'enterprise_customer',
                    'enterprise_customer_catalog',
                    'notify_email',
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
            },

            setupToggleListeners: function() {
                this.listenTo(this.model, 'change:coupon_type', this.toggleCouponTypeField);
                this.listenTo(this.model, 'change:voucher_type', this.toggleVoucherTypeField);
                this.listenTo(this.model, 'change:code', this.toggleCodeField);
                this.listenTo(this.model, 'change:quantity', this.toggleQuantityField);
            },

            cancelButtonClicked: function() {
                this.model.set(this._initAttributes);
            }
        });
    }
);
