define([
        'jquery',
        'underscore.string',
        'backbone',
    ],
    function ($,
              _s,
              Backbone) {
        'use strict';

        return Backbone.View.extend({
            events: {
                'click .payment-button': 'checkout'
            },

            setSku: function (sku) {
                var button = this.$('.payment-button'),
                    href = _s.sprintf('/basket/single-item/?sku=%s', sku);
                button.attr('href', href);
            }
        });
    });
