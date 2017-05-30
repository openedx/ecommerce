define([
    'jquery',
    'underscore.string',
    'backbone'
],
    function($,
              _s,
              Backbone) {
        'use strict';

        return Backbone.View.extend({
            events: {
                'click .payment-button': 'checkout'
            },

            setSku: function(sku) {
                var button = this.$('.payment-button'),
                    code = window.location.search.substring(1).split('=')[1],
                    href;
                if (code === undefined) {
                    href = _s.sprintf('/basket/single-item/?sku=%s', sku);
                } else {
                    href = _s.sprintf('/coupons/redeem/?code=%s&sku=%s', code, sku);
                }
                button.attr('href', href);
            }
        });
    });
