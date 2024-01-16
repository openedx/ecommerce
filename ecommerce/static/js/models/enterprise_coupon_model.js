define([
    'backbone',
    'backbone.validation',
    'models/coupon_model',
    'underscore',
    'backbone.relational'
],
    function(Backbone,
              BackboneValidation,
              CouponModel,
              _) {
        'use strict';

        _.extend(Backbone.Validation.messages, {
            required: gettext('This field is required.'),
            number: gettext('This value must be a number.'),
            date: gettext('This value must be a date.'),
            email: gettext('This value must be a valid email.')
        });
        _.extend(Backbone.Model.prototype, Backbone.Validation.mixin);

        return CouponModel.extend({
            urlRoot: '/api/v2/enterprise/coupons/',

            defaults: {
                category: {id: 3, name: 'Affiliate Promotion'},
                code: '',
                id: null,
                max_uses: 1,
                price: 0,
                quantity: 1,
                enterprise_catalog_content_metadata_url: null,
                contract_discount_type: 'Percentage',
                contract_discount_value: null,
                prepaid_invoice_amount: null,
                sales_force_id: null,
                salesforce_opportunity_line_item: null
            },

            couponValidation: {
                enterprise_customer: {required: true},
                enterprise_customer_catalog: {required: true},
                notify_email: {
                    pattern: 'email',
                    required: false
                },
                contract_discount_value: {
                    required: function() {
                        return !this.attributes.editing;
                    },
                    pattern: 'number'
                },
                prepaid_invoice_amount: {
                    required: function() {
                        return this.get('contract_discount_type') === 'Absolute';
                    },
                    pattern: 'number'
                },
                sales_force_id: {
                    required: false,
                    pattern: 'sales_force_id'
                },
                salesforce_opportunity_line_item: {
                    required: true,
                    pattern: 'salesforce_opportunity_line_item'
                }
            },

            initialize: function() {
                this.on('change:payment_information', this.updatePaymentInformation);
            }
        });
    }
);
