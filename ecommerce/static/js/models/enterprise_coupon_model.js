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
                quantity: 1
            },

            couponValidation: {
                enterprise_customer: {required: true},
                enterprise_customer_catalog: {required: true},
                notify_email: {
                    pattern: 'email',
                    required: false
                }
            },

            initialize: function() {
                this.on('change:payment_information', this.updatePaymentInformation);
            }
        });
    }
);
