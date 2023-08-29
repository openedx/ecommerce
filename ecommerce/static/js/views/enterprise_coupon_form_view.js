/* eslint no-underscore-dangle: ["error", { "allow": ["_initAttributes", "_super"] }] */

define([
    'jquery',
    'backbone',
    'backbone.super',
    'backbone.validation',
    'ecommerce',
    'underscore',
    'text!templates/enterprise_coupon_form.html',
    'views/coupon_form_view',
    'autocomplete'
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
                'input[name=inactive]': {
                    observe: 'inactive',
                    onGet: function(val) {
                        return val ? 'inactive' : 'active';
                    },
                    onSet: function(val) {
                        return val === 'inactive';
                    }
                },
                'input[name=enterprise_customer]': {
                    observe: 'enterprise_customer',
                    onGet: function(val) {
                        this.fetchEnterpriseCustomerCatalogs();
                        return _.isUndefined(val) || _.isNull(val) ? '' : val.name;
                    },
                    onSet: function(rawInput) {
                        var customer;
                        // fetch record from endpoint
                        if (_.isString(rawInput) && rawInput.length >= 3) {
                            ecommerce.coupons.enterprise_customers.fetch({data: {startswith: rawInput}});
                        }
                        customer = ecommerce.coupons.enterprise_customers.findWhere({name: rawInput});
                        return _.isUndefined(customer) ? null : customer.toJSON();
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
                'input[name=prepaid_invoice_amount]': {
                    observe: 'prepaid_invoice_amount',
                    setOptions: {
                        validate: true
                    },
                    onSet: function(val) {
                        if (val === '') {
                            return null;
                        }
                        return val;
                    }
                }
            },

            events: {
                'focus [name=enterprise_customer]': 'enterpriseCustomerAutocomplete',
                'keydown [name=enterprise_customer]': 'inputKeydown',
                // catch value after autocomplete
                'change [name=benefit_type]': 'changeLimitForBenefitValue',
                'change [name=invoice_discount_type]': 'changeLimitForInvoiceDiscountValue',
                'change [name=contract_discount_type]': 'changeLimitForContractDiscountValue',
                'change [name=invoice_type]': 'toggleInvoiceFields',
                'change [name=tax_deduction]': 'toggleTaxDeductedSourceField',
                'click .external-link': 'routeToLink',
                'click #cancel-button': 'cancelButtonClicked',
                'click .submit-add-more': 'submitAndAddMore',
                'change select[name=enterprise_customer_catalog]': 'updateEnterpriseCatalogDetailsLink'
            },

            updateEnterpriseCatalogDetailsLink: function() {
                var enterpriseAPIURL = this.model.get('enterprise_catalog_content_metadata_url'),
                    enterpriseCatalog = this.$('[name=enterprise_customer_catalog]').val();

                if (enterpriseCatalog) {
                    this.$('#enterprise-catalog-details')
                        .attr('href', enterpriseAPIURL)
                        .addClass('external-link')
                        .removeClass('hidden');
                } else {
                    this.$('#enterprise-catalog-details')
                        .removeAttr('href')
                        .removeClass('external-link')
                        .addClass('hidden');
                }
            },

            submitAndAddMore: function() {
                this.$('.submit-add-more').attr('data-url', 'new');
                $('form.coupon-form-view').submit();
            },

            enterpriseCustomerAutocomplete: function() {
                var self = this;

                $('#enterprise-customer').autocomplete({
                    collection: ecommerce.coupons.enterprise_customers,
                    attr: 'name',
                    noCase: true,
                    width: this.$el.find('#enterprise-customer').outerWidth(true),
                    ul_css: {padding: 0},
                    onselect: self.autocompleteSelect,
                    max_results: 15
                });
            },

            inputKeydown: function(e) {
                // Stop submitting form on ENTER press
                if (e.keyCode === 13 || e.keyCode === 9) {
                    e.preventDefault();
                    e.stopPropagation();
                }
            },

            autocompleteSelect: function(model) {
                $('#enterprise-customer').val(model.label()).trigger('change');
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
                var isContractDiscountPercentage = this.$(
                    '[name=contract_discount_type]:checked').val() === 'Percentage',
                    maxValue = isContractDiscountPercentage ? '100' : '';
                this.setLimitToElement(this.$('[name=contract_discount_value]'), maxValue, 0);
            },

            getEditableAttributes: function() {
                return [
                    'benefit_value',
                    'category',
                    'end_date',
                    'enterprise_customer',
                    'enterprise_customer_catalog',
                    'notify_email',
                    'inactive',
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
                    'prepaid_invoice_amount',
                    'sales_force_id',
                    'salesforce_opportunity_line_item'
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
                if (this.$('[name=contract_discount_type]:checked').val() === 'Percentage') {
                    this.setLimitToElement(this.$('[name=contract_discount_value]'), 100, 0);
                }
                this._super();
                if (this.editing) {
                    this.$('.submit-add-more').hide();
                } else {
                    this.$('.submit-add-more').html(gettext('Create and Add More'));
                }
                return this;
            },
            /**
             * Override default saveSuccess.
             */
            saveSuccess: function(model, response) {
                var nextUrl = $('.submit-add-more').attr('data-url');
                if (this.editing || _.isUndefined(nextUrl)) {
                    nextUrl = response.coupon_id ? response.coupon_id.toString() : response.id.toString();
                    this.goTo(nextUrl);
                } else {
                    $('.submit-add-more').removeAttr('data-url');
                    // Backbone's history/router will do nothing when trying to load the same URL
                    // in case of create and add more that's why force the route instead.
                    Backbone.history.loadUrl(nextUrl);
                }
            }
        });
    }
);
