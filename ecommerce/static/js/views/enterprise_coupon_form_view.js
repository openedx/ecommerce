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
                        return _.isEmpty(val) ? null : {
                            id: val,
                            name: $('select[name=enterprise_customer] option:selected').text()
                        };
                    }
                },
                'select[name=enterprise_customer_catalog]': {
                    observe: 'enterprise_customer_catalog',
                    selectOptions: {
                        collection: function() {
                            return ecommerce.coupons.enterprise_customer_catalogs;
                        },
                        defaultOption: {uuid: '', title: ''},
                        labelPath: 'title',
                        valuePath: 'uuid'
                    },
                    setOptions: {
                        validate: true
                    },
                    onGet: function(val) {
                        this.updateEnterpriseCatalogDetailsLink();
                        return _.isUndefined(val) || _.isNull(val) ? '' : val;
                    },
                    onSet: function(val) {
                        return !_.isEmpty(val) && _.isString(val) ? val : null;
                    }
                },
                'input[name=notify_email]': {
                    observe: 'notify_email',
                    onSet: function(val) {
                        return val === '' ? null : val;
                    }
                },
                'input[name=contract_discount_type]': {
                    observe: 'contract_discount_type'
                },
                '.contract-discount-addon': {
                    observe: 'contract_discount_type',
                    onGet: function(val) {
                        return this.toggleDollarPercentIcon(val);
                    }
                },
                'input[name=contract_discount_value]': {
                    observe: 'contract_discount_value',
                    setOptions: {
                        validate: true
                    },
                    onSet: function(val) {
                        if (val === '') {
                            return null;
                        }
                        return val;
                    }
                },
            },

            events: {
                // catch value after autocomplete
                'change [name=benefit_type]': 'changeLimitForBenefitValue',
                'change [name=invoice_discount_type]': 'changeLimitForInvoiceDiscountValue',
                'change [name=contract_discount_type]': 'changeLimitForContractDiscountValue',
                'change [name=invoice_type]': 'toggleInvoiceFields',
                'change [name=tax_deduction]': 'toggleTaxDeductedSourceField',
                'click .external-link': 'routeToLink',
                'click #cancel-button': 'cancelButtonClicked',
                'change select[name=enterprise_customer_catalog]': 'updateEnterpriseCatalogDetailsLink'
            },

            updateEnterpriseCatalogDetailsLink: function() {
                var enterpriseAPIURL = this.model.get('enterprise_catalog_url'),
                    enterpriseCatalog = this.$('[name=enterprise_customer_catalog]').val();

                if (enterpriseCatalog) {
                    this.$('#enterprise-catalog-details')
                        .attr('href', enterpriseAPIURL + enterpriseCatalog)
                        .addClass('external-link')
                        .removeClass('hidden');
                } else {
                    this.$('#enterprise-catalog-details')
                        .removeAttr('href')
                        .removeClass('external-link')
                        .addClass('hidden');
                }
            },

            fetchEnterpriseCustomerCatalogs: function() {
                var self = this;
                var enterpriseCustomer = this.model.get('enterprise_customer');

                if (!_.isEmpty(enterpriseCustomer) && !_.isEmpty(enterpriseCustomer.id)) {
                    ecommerce.coupons.enterprise_customer_catalogs.fetch(
                        {
                            data: {
                                enterprise_customer: enterpriseCustomer.id
                            },
                            success: function() {
                                self.toggleEnterpriseCatalogField(false);
                            },
                            error: function() {
                                self.toggleEnterpriseCatalogField(true);
                            }
                        }
                    );
                } else {
                    self.toggleEnterpriseCatalogField(true);
                }
            },

            toggleEnterpriseCatalogField: function(disable) {
                this.$('select[name=enterprise_customer_catalog]').attr('disabled', disable);
            },

            changeLimitForContractDiscountValue: function() {
                console.log("i'm in changeLimitForContractDiscountValue");
                var isContractDiscountPercentage = this.$('[name=contract_discount_type]:checked').val() === 'Percentage',
                    maxValue = isContractDiscountPercentage ? '100' : '';
                console.log("isContractDiscountPercentage is: ");
                console.log(isContractDiscountPercentage);
                this.setLimitToElement(this.$('[name=contract_discount_type]'), maxValue, 1);
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
                    'email_domains',
                    'contract_discount_value',
                    'contract_discount_type',
                ];
            },

            setupToggleListeners: function() {
                this.listenTo(this.model, 'change:coupon_type', this.toggleCouponTypeField);
                this.listenTo(this.model, 'change:voucher_type', this.toggleVoucherTypeField);
                this.listenTo(this.model, 'change:code', this.toggleCodeField);
                this.listenTo(this.model, 'change:quantity', this.toggleQuantityField);
                this.listenTo(this.model, 'change:enterprise_customer', this.fetchEnterpriseCustomerCatalogs);
            },

            cancelButtonClicked: function() {
                this.model.set(this._initAttributes);
            },

            render: function() {
                console.log("this is the render of coupon form view:")
                console.log(this.model);
                // if (this.editing) {
                //     console.log("get the contract_discount_type from somewhere");
                //     // if this.model.get('contract_discount_type') {
                //     //     this.model.set({
                //     //     contract_discount_type: 'Percentage',
                //     // })
                //     // }c
                // } else {
                //     this.model.set({
                //         contract_discount_type: 'Percentage',
                //         contract_discount_value: null,
                //     })
                // }

                if (this.$('[name=contract_discount_type]:checked').val() === 'Percentage') {
                    this.setLimitToElement(this.$('[name=contract_discount_value]'), 100, 1);
                }

                this._super();
                return this;
            }
        });
    }
);
