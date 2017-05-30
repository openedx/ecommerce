/**
 * Basket page scripts.
 **/

define([
    'jquery'
],
    function($) {
        'use strict';

        function trackPurchase(orderId, totalAmount, currency) {
            window.analytics.track('Order Completed', {
                orderId: orderId,
                total: totalAmount,
                currency: currency
            });
        }

        function onReady() {
            var $el = $('#receipt-container'),
                orderId = $el.data('order-id'),
                totalAmount = $el.data('total-amount'),
                currency = $el.data('currency');
            if (orderId) {
                trackPurchase(orderId, totalAmount, currency);
            }
        }

        $(document).ready(onReady);

        return {
            onReady: onReady
        };
    }
);
