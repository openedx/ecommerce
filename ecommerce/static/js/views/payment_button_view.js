define([
        'jquery',
        'underscore',
        'underscore.string',
        'backbone',
        'js-cookie'
    ],
    function ($,
              _,
              _s,
              Backbone
    ) {
        'use strict';

        return Backbone.View.extend({

            initialize: function () {
                this.button = this.$('.payment-button');
            },

            setSku: function (sku) {
                var code = window.location.search.substring(1).split('=')[1],
                    href;
                if (code === undefined) {
                    href = _s.sprintf('/basket/single-item/?sku=%s', sku);
                } else {
                    href = _s.sprintf('/coupons/redeem/?code=%s&sku=%s', code, sku);
                }
                this.button.attr('href', href);
            }
        });
    });
