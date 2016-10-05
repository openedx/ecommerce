define([
        'jquery',
        'backbone',
        'underscore',
        'underscore.string',
        'utils/analytics_utils',
        'js-cookie',
        'date-utils',
        'bootstrap',
        'jquery-url'
    ],
function ($,
          Backbone,
          _,
          _s,
          AnalyticsUtils,
          Cookies) {
    'use strict';

    return Backbone.View.extend({
        el: '#receipt-container',

        initialize: function (options) {
            this.orderNumber = options.orderNumber;
        },

        trackPurchase: function() {
            $.ajax({
                url: _s.sprintf('/api/v2/orders/%s', this.orderNumber),
                method: 'GET',
                headers: {
                    'X-CSRFToken': Cookies.get('ecommerce_csrftoken')
                },
                success: this.triggerCompletedPurchase
            });
        },

        triggerCompletedPurchase: function(data) {
            AnalyticsUtils.trackingModel.trigger('segment:track', 'Completed Purchase', {
                currency: data.currency,
                orderId: data.number,
                total: data.total_excl_tax
            });
        },

        render: function () {
            // After fully rendering the template, attach analytics click handlers
            AnalyticsUtils.instrumentClickEvents();

            if(this.$el.attr('data-is-payment-complete') === 'True') {
                // Fire analytics event that purchase has completed
                this.trackPurchase();
            }
        }
    });
});
