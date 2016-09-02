define([
        'jquery',
        'underscore',
        'backbone',
        'js-cookie'
    ],
    function ($,
              _,
              Backbone
    ) {
        'use strict';

        return Backbone.View.extend({

            initialize: function () {
                this.button = this.$el.find('.payment-button');
            },

            setSku: function (sku) {
                var code = window.location.search.substring(1).split('=')[1];
                this.button.attr('href', '/coupons/redeem/?code=' + code + '&sku=' + sku);
            }
        });
    });
